"""Avg-evo loop contracts: normalize, dedupe, rotate, patch-gate, memory.

The loop's whole value is acting without spamming: malformed 1B output must
normalize, repeats must collapse, patches must gate on validation, and every
decision must land in evolution memory.
"""
import json
from pathlib import Path

import pytest

from self_evolution.avg_evo import analyzer
from self_evolution.avg_evo import patcher


class FakeLLM:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def complete(self, prompt, max_tokens=256, temperature=0.2, **kw):
        self.calls.append(prompt)
        return self.text


@pytest.fixture
def base(tmp_path):
    (tmp_path / "tools" / "index").mkdir(parents=True)
    (tmp_path / "tools" / "index" / "summaries.json").write_text(
        json.dumps({"terminal": "run shell commands", "read_file": "read a file"}))
    return tmp_path


class TestNormalize:
    def test_garbage_issue_dropped(self):
        out = analyzer.analyze("u", "a", "", llm_client=FakeLLM('{"issues": [{"nope": 1}], "hard_problem": {}}'))
        assert out["issues"] == []

    def test_bad_severity_coerced(self):
        out = analyzer.analyze("u", "a", "",
                               llm_client=FakeLLM('{"issues": [{"type": "error", "severity": "CRITICAL", "fix": "x"}]}'))
        assert out["issues"][0]["severity"] == "med"

    def test_fixless_issue_dropped(self):
        out = analyzer.analyze("u", "a", "",
                               llm_client=FakeLLM('{"issues": [{"type": "error", "severity": "low"}]}'))
        assert out["issues"] == []

    def test_no_llm_error_text_heuristic(self):
        out = analyzer.analyze("u", "tool failed badly", "", llm_client=None)
        assert len(out["issues"]) == 1

    def test_no_llm_clean_is_quiet(self):
        out = analyzer.analyze("u", "all good", "", llm_client=None)
        assert out["issues"] == [] and out["hard_problem"]["queued"] is False


class TestDedupe:
    BODY = '{"issues": [{"type": "error", "severity": "low", "fix": "retry terminal with escaped path"}], "hard_problem": {}}'

    def test_repeat_collapses(self, base):
        llm = FakeLLM(self.BODY)
        r1 = analyzer.handle_response(base, "u", "a", "", llm_client=llm)
        r2 = analyzer.handle_response(base, "u", "a", "", llm_client=llm)
        assert r1["new_pending"] == 1
        assert r2["new_pending"] == 0  # same issue: no second pending file
        assert len(list((base / "self_evolution" / "patches" / "pending").glob("*.json"))) == 1

    def test_fixes_log_rotates(self, base):
        log = base / "self_evolution" / "queue" / "fixes.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("\n".join(f'{{"n": {i}}}' for i in range(505)) + "\n")
        analyzer._rotate(log, 500)
        assert len(log.read_text().splitlines()) == 500


class TestPatcher:
    def test_no_llm_rejects(self, base):
        p = base / "self_evolution" / "patches" / "pending" / "t.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"key": "k1", "issue": {"type": "format", "severity": "low",
                                                       "fix": "SET tools/index/summaries.json[terminal] = run commands"}}))
        out = patcher.apply_pending(base, dry_run=False, llm_client=None)
        assert any("rejected" in o for o in out)
        assert not p.exists()
        mem = (base / "self_evolution" / "memory.jsonl").read_text()
        assert "rejected" in mem

    def test_valid_summary_applies(self, base):
        fake = FakeLLM('{"valid": true, '
                       '"fixed_patch": "SET tools/index/summaries.json[terminal] = run shell commands fast", '
                       '"reason": "sharper"}')
        p = base / "self_evolution" / "patches" / "pending" / "t.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"key": "k2", "issue": {"type": "format", "severity": "low",
                                                       "fix": "sharpen terminal summary"}}))
        out = patcher.apply_pending(base, dry_run=False, llm_client=fake)
        assert any("applied" in o for o in out), out
        data = json.loads((base / "tools" / "index" / "summaries.json").read_text())
        assert data["terminal"] == "run shell commands fast"
        assert not p.exists()
        assert (base / "self_evolution" / "patches" / "applied" / "t.json").exists()

    def test_non_set_format_deferred(self, base):
        fake = FakeLLM('{"valid": true, "fixed_patch": "rewrite the whole scheduler", "reason": "ok"}')
        p = base / "self_evolution" / "patches" / "pending" / "t.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"key": "k3", "issue": {"type": "error", "severity": "med",
                                                       "fix": "rewrite the whole scheduler"}}))
        out = patcher.apply_pending(base, dry_run=False, llm_client=fake)
        assert any("deferred" in o for o in out)
        # deferred stays pending for human/heavy review
        assert p.exists()

    def test_unknown_tool_refused(self, base):
        fake = FakeLLM('{"valid": true, '
                       '"fixed_patch": "SET tools/index/summaries.json[nope] = whatever", '
                       '"reason": "ok"}')
        p = base / "self_evolution" / "patches" / "pending" / "t.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"key": "k4", "issue": {"type": "format", "severity": "low", "fix": "x"}}))
        out = patcher.apply_pending(base, dry_run=False, llm_client=fake)
        assert any("failed" in o for o in out)


class TestHook:
    def test_disabled_config_fires_nothing(self, tmp_path):
        (tmp_path / "self_evolution").mkdir()
        (tmp_path / "self_evolution" / "config.yaml").write_text("avg_evo:\n  enabled: false\n")
        from self_evolution import hook
        hook._CONFIG_CACHE.clear()
        hook.on_response(tmp_path, "u", "a")
        import time
        time.sleep(0.2)
        assert not (tmp_path / "self_evolution" / "queue").exists()

    def test_trace_builder(self):
        from self_evolution.hook import _trace_from_messages
        msgs = [{"role": "user", "content": "hi"},
                {"role": "assistant", "tool_calls": [{"function": {"name": "terminal"}}]},
                {"role": "tool", "name": "terminal", "content": "ok " * 200}]
        trace = _trace_from_messages(msgs)
        assert "terminal" in trace and len(trace) <= 900


class TestDeadLetter:
    def test_three_strikes_parks(self, base):
        from self_evolution.avg_evo import patcher as P
        mem = base / "self_evolution" / "memory.jsonl"
        mem.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            with open(mem, "a") as f:
                f.write(json.dumps({"key": "k9", "kind": "deferred"}) + "\n")
        fake = FakeLLM('{"valid": true, "fixed_patch": "vague mush", "reason": "ok"}')
        p = base / "self_evolution" / "patches" / "pending" / "t.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"key": "k9", "issue": {"type": "format", "severity": "low", "fix": "x"}}))
        out = P.apply_pending(base, dry_run=False, llm_client=fake)
        assert any("dead-lettered" in o for o in out), out
        assert not p.exists()
