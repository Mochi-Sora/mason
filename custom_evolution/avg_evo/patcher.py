"""Micro-patcher: validate avg-evo fixes, apply safe ones, record everything.

Allowlist (auto-apply): tools/index/summaries.json — one-line manifest edits
are low-blast-radius and machine-verifiable (listing still builds).
Everything else stays pending for human / nightly-heavy review.

Each decision lands in custom_evolution/memory.jsonl (the evolution memory):
{ts, key, kind: applied|rejected|failed|deferred, target, summary, outcome}.
The nightly reads it so it never re-proposes what was decided.

Applied patches commit to git (revertable by construction) when base is a repo.
"""
import datetime
import json
import pathlib
import re
import subprocess

# target -> handler. Only these paths may change without a human.
ALLOW = {"tools/index/summaries.json"}

MAX_DEFERRED_RETRIES = 3

SET_RE = re.compile(r"SET\s+tools/index/summaries\.json\[(?P<name>[A-Za-z0-9_\-]+)\]\s*=\s*(?P<text>.+)",
                    re.S)


def _deferral_count(base: pathlib.Path, key: str) -> int:
    try:
        n = 0
        for line in (base / "custom_evolution" / "memory.jsonl").read_text().splitlines():
            try:
                j = json.loads(line)
                if j.get("key") == key and j.get("kind") == "deferred":
                    n += 1
            except Exception:
                continue
        return n
    except OSError:
        return 0


def _mem(base: pathlib.Path, key: str, kind: str, target: str, summary: str, outcome: str = "") -> None:
    try:
        with open(base / "custom_evolution" / "memory.jsonl", "a") as f:
            f.write(json.dumps({"ts": datetime.datetime.utcnow().isoformat(), "key": key,
                                "kind": kind, "target": target,
                                "summary": summary[:300], "outcome": outcome[:300]}) + "\n")
    except OSError:
        pass


def _git_commit(base: pathlib.Path, target: str, summary: str) -> str:
    """Commit one applied patch; returns sha or '' (non-repo / failure = no-op)."""
    try:
        if not (base / ".git").is_dir():
            return ""
        subprocess.run(["git", "add", target], cwd=base, capture_output=True, timeout=30)
        r = subprocess.run(["git", "commit", "-q", "-m", f"evo: {summary[:120]}"],
                           cwd=base, capture_output=True, timeout=60)
        if r.returncode != 0:
            return ""
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=base, capture_output=True, timeout=30).stdout.decode().strip()
        return sha
    except Exception:
        return ""


def _apply_summary(base: pathlib.Path, name: str, text: str) -> tuple[bool, str]:
    """Replace one summaries.json line; verify JSON + listing still builds."""
    idx = base / "tools" / "index" / "summaries.json"
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"summaries.json unreadable: {e}"
    if name not in data:
        return False, f"{name} not in summaries.json"
    text = text.strip().strip('"').strip("'").rstrip(".")
    if not (3 < len(text) <= 120):
        return False, "replacement line fails length contract"
    data[name] = text
    try:
        idx.write_text(json.dumps(dict(sorted(data.items())), indent=1, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    except OSError as e:
        return False, f"write failed: {e}"
    try:
        from tools.tool_search_catalog import _summaries_override, refresh_summaries_cache
        refresh_summaries_cache()
        _ = _summaries_override()
    except Exception as e:
        return False, f"listing verification failed: {e}"
    return True, f"{name}: {text}"


def _validate(base: pathlib.Path, fix: str, llm_client, timeout: int) -> tuple[bool, str, str]:
    """1B gate: returns (valid, fixed_patch, reason). No LLM = no auto-apply."""
    if llm_client is None:
        return False, "", "no 1B client — human review required"
    try:
        from custom_evolution.tasks.patch_apply_task import build_prompt
        prompt = build_prompt(fix, "tools/index/summaries.json")
        try:
            raw = llm_client.complete(prompt, max_tokens=200, temperature=0.1, timeout=timeout)
        except TypeError:
            raw = llm_client.complete(prompt, max_tokens=200, temperature=0.1)
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return False, "", "validator returned no JSON"
        j = json.loads(m.group(0))
        return bool(j.get("valid")), str(j.get("fixed_patch", "")), str(j.get("reason", ""))
    except Exception as e:
        return False, "", f"validator error: {e}"[:200]


def apply_pending(base: pathlib.Path, dry_run=True, llm_client=None, timeout: int = 60) -> list[str]:
    """Process patches/pending. Returns human-readable outcome lines."""
    base = pathlib.Path(base)
    pending_dir = base / "custom_evolution" / "patches" / "pending"
    applied_dir = base / "custom_evolution" / "patches" / "applied"
    applied_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[str] = []
    for p in sorted(pending_dir.glob("*.json")):
        try:
            entry = json.loads(p.read_text())
        except Exception:
            p.unlink(missing_ok=True)
            continue
        iss = entry.get("issue") or {}
        key = entry.get("key", p.stem)
        fix = str(iss.get("fix", ""))
        if dry_run:
            outcomes.append(f"{p.name}: queued ({fix[:80]})")
            continue
        valid, fixed, reason = _validate(base, fix, llm_client, timeout)
        if not valid:
            _mem(base, key, "rejected", "tools/index/summaries.json", fix, reason)
            p.unlink(missing_ok=True)
            outcomes.append(f"{p.name}: rejected ({reason[:80]})")
            continue
        m = SET_RE.search(fixed)
        if not m:
            if _deferral_count(base, key) >= MAX_DEFERRED_RETRIES:
                # Dead letter: three nights, still not actionable — park it in
                # applied/ so the nightly stops spending 1B calls on it.
                _mem(base, key, "deferred", "tools/index/summaries.json", fix,
                     "dead-lettered after 3 retries; human/heavy review only")
                try:
                    p.rename(applied_dir / p.name)
                except OSError:
                    p.unlink(missing_ok=True)
                outcomes.append(f"{p.name}: dead-lettered (3 failed shapings)")
                continue
            _mem(base, key, "deferred", "tools/index/summaries.json", fix,
                 "no SET summaries.json[name] = ... edit; needs human/heavy")
            outcomes.append(f"{p.name}: deferred (not a summaries edit)")
            continue
        ok, msg = _apply_summary(base, m.group("name"), m.group("text"))
        if not ok:
            _mem(base, key, "failed", "tools/index/summaries.json", fix, msg)
            outcomes.append(f"{p.name}: failed ({msg[:80]})")
            continue
        sha = _git_commit(base, "tools/index/summaries.json", msg)
        _mem(base, key, "applied", "tools/index/summaries.json", fix,
             f"{msg} commit={sha or 'n/a'}")
        dest = applied_dir / p.name
        try:
            p.rename(dest)
        except OSError:
            p.unlink(missing_ok=True)
        outcomes.append(f"{p.name}: applied ({msg[:80]}) commit={sha or 'n/a'}")
    return outcomes
