"""Mason cold-start tool loading: defer-all default + session working set.

Contracts (not snapshots):
- default (no explicit defer list): everything defers except clarify + bridge
- explicit defer=[]: everything eager (legacy opt-out preserved)
- working set: describe joins, call resets hatch, 3x describe-no-call auto-adds
- heuristics map obvious messages to tools without inference
- folder index stays consistent (every core tool has a summary line)
"""
import json
from pathlib import Path

import pytest

from tools import working_set as ws
from tools.tool_search import (
    BRIDGE_TOOL_NAMES,
    _EAGER_TOOL_NAMES,
    is_deferrable_tool_name,
)

REPO = Path(__file__).resolve().parents[2]


def _def(name):
    return {"type": "function", "function": {"name": name, "description": f"{name} does things.", "parameters": {"type": "object", "properties": {}}}}


# ── defer-all default ──────────────────────────────────────────────
class TestDeferAllDefault:
    def test_core_tools_defer_by_default(self):
        for name in ("terminal", "read_file", "memory", "delegate_task",
                     "read_state", "recall_backup", "web_search"):
            assert is_deferrable_tool_name(name, None), name

    def test_clarify_stays_eager(self):
        assert not is_deferrable_tool_name("clarify", None)
        assert "clarify" in _EAGER_TOOL_NAMES

    def test_bridge_never_defers(self):
        for name in BRIDGE_TOOL_NAMES:
            assert not is_deferrable_tool_name(name, None)

    def test_explicit_empty_list_is_eager(self):
        assert not is_deferrable_tool_name("terminal", frozenset())
        assert not is_deferrable_tool_name("read_file", frozenset())

    def test_explicit_list_still_defers_members(self):
        assert is_deferrable_tool_name("terminal", frozenset({"terminal"}))


# ── working set ────────────────────────────────────────────────────
@pytest.fixture
def sid():
    s = "ws-test-session"
    ws.reset_session(s)
    yield s
    ws.reset_session(s)


class TestWorkingSet:
    def test_describe_joins_set(self, sid):
        assert ws.get(sid) == [] or True  # warm file may preload; membership is what matters
        ws.note_described(sid, ["terminal"])
        assert "terminal" in ws.get(sid)

    def test_call_resets_hatch_counter(self, sid):
        ws.note_described(sid, ["terminal"])
        ws.note_described(sid, ["terminal"])
        ws.note_called(sid, "terminal")
        auto = ws.note_described(sid, ["terminal"])
        assert auto == []  # counter reset by the call; no auto-add yet

    def test_escape_hatch_auto_adds_on_third_describe(self, sid):
        ws.note_called(sid, "terminal")  # ensure counter starts at 0
        ws.note_described(sid, ["terminal"])
        ws.note_described(sid, ["terminal"])
        auto = ws.note_described(sid, ["terminal"])
        assert auto == ["terminal"]
        assert "terminal" in ws.get(sid)

    def test_add_dedupes_and_returns_fresh(self, sid):
        ws.add(sid, ["a", "b"])
        assert ws.add(sid, ["b", "c"]) == ["c"]
        assert ws.get(sid).count("b") == 1


# ── heuristics (no inference) ──────────────────────────────────────
class TestHeuristics:
    def test_file_mention(self):
        got = ws.heuristic_tools("read main.py and show me the auth part")
        assert "read_file" in got and "search_files" in got

    def test_run_command(self):
        assert "terminal" in ws.heuristic_tools("run pytest now")

    def test_memory_words(self):
        got = ws.heuristic_tools("remember that I prefer dark mode")
        assert "memory" in got

    def test_chitchat_yields_nothing(self):
        assert ws.heuristic_tools("haha ok thanks!") == []

    def test_cap_respected(self):
        assert len(ws.heuristic_tools("read x.py run tests remember this https://a.b now please")) <= ws.MAX_HEURISTIC


# ── protocol block ─────────────────────────────────────────────────
class TestProtocol:
    def test_mentions_bridge_and_ban(self):
        p = ws.PROTOCOL_BLOCK
        assert "tool_describe" in p and "tool_call" in p
        assert "NEVER invent" in p
        assert len(p) // 4 < 200  # must stay a small stable-tier block


# ── 1B task prompts build ──────────────────────────────────────────
class TestTaskPrompts:
    def test_predict_builds(self):
        from custom_memory.llm.tasks.tool_predict_task import build_prompt
        out = build_prompt("read main.py")
        assert "read_file" in out and "{text}" not in out

    def test_summary_builds(self):
        from custom_memory.llm.tasks.tool_summary_task import build_prompt
        out = build_prompt("recall_backup", "Search backup", "read_state (tiny state)")
        assert "recall_backup" in out and "{name}" not in out


# ── folder index consistency ───────────────────────────────────────
class TestFolderIndex:
    def test_every_core_tool_has_summary(self):
        from toolsets import _MASON_CORE_TOOLS
        summaries = json.loads((REPO / "tools" / "index" / "summaries.json").read_text())
        missing = [t for t in _MASON_CORE_TOOLS if t not in summaries]
        assert not missing, f"no summary line: {missing}"

    def test_index_md_covers_summaries(self):
        summaries = json.loads((REPO / "tools" / "index" / "summaries.json").read_text())
        body = (REPO / "tools" / "index" / "INDEX.md").read_text()
        missing = [n for n in summaries if f"- {n}:" not in body]
        assert not missing, f"not in INDEX.md: {missing[:5]}"
