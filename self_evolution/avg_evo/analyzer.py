"""Avg-evo analyzer — 1B per-response fix + queue.

Output contract (enforced by _normalize): every issue is
{type, severity, fix}; hard_problem is {queued, title, reason}.
Dedupe: an issue identical (type + fix head) to anything in the last
FIXES_RETAIN lines, pending patches, hard queue, or evolution memory is
dropped — a recurring error must not flood the queues every turn.
"""
import hashlib
import json
import pathlib
import datetime
from self_evolution.tasks.avg_evo_task import build_prompt

FIXES_RETAIN = 500
DEDUP_WINDOW = 200
TYPES = {"error", "inaccuracy", "format", "missing_ctx"}
SEVERITIES = {"low", "med", "high"}


def _norm_issue(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    typ = str(raw.get("type", "")).strip().lower()
    sev = str(raw.get("severity", "")).strip().lower()
    fix = str(raw.get("fix", "")).strip()
    if typ not in TYPES:
        typ = "error"
    if sev not in SEVERITIES:
        sev = "med" if typ == "error" else "low"
    if not fix:
        return None
    return {"type": typ, "severity": sev, "fix": fix[:300]}


def _norm_hard(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    queued = raw.get("queued") is True
    return {"queued": queued,
            "title": str(raw.get("title", ""))[:100] if queued else "",
            "reason": str(raw.get("reason", ""))[:300] if queued else ""}


def _issue_key(iss: dict) -> str:
    return hashlib.sha1(f"{iss['type']}|{iss['fix'][:120]}".encode()).hexdigest()[:16]


def _recent_keys(base: pathlib.Path) -> set:
    keys = set()
    try:
        lines = (base / "self_evolution" / "queue" / "fixes.jsonl").read_text().splitlines()
        for line in lines[-DEDUP_WINDOW:]:
            try:
                iss = (json.loads(line) or {}).get("issue") or {}
                if iss.get("type") and iss.get("fix"):
                    keys.add(hashlib.sha1(
                        f"{iss['type']}|{str(iss['fix'])[:120]}".encode()).hexdigest()[:16])
            except Exception:
                continue
    except OSError:
        pass
    for d in (base / "self_evolution" / "patches" / "pending",
              base / "self_evolution" / "patches" / "applied"):
        try:
            for p in d.glob("*.json"):
                try:
                    iss = (json.loads(p.read_text()) or {}).get("issue") or {}
                    if iss.get("type") and iss.get("fix"):
                        keys.add(hashlib.sha1(
                            f"{iss['type']}|{str(iss['fix'])[:120]}".encode()).hexdigest()[:16])
                except Exception:
                    continue
        except OSError:
            continue
    try:
        mem = base / "self_evolution" / "memory.jsonl"
        if mem.exists():
            for line in mem.read_text().splitlines()[-DEDUP_WINDOW:]:
                try:
                    keys.add(str((json.loads(line) or {}).get("key", "")))
                except Exception:
                    continue
    except OSError:
        pass
    return keys


def analyze(user_msg: str, assistant_final: str, tool_trace: str = "", llm_client=None,
            timeout: int = 45) -> dict:
    prompt = build_prompt(user_msg, assistant_final, tool_trace)
    fallback = {"issues": [], "hard_problem": {"queued": False, "title": "", "reason": "llm unavailable"}}
    if llm_client is None:
        if "error" in assistant_final.lower() or "failed" in assistant_final.lower():
            return {"issues": [{"type": "error", "severity": "med", "fix": "retry tool or clarify"}],
                    "hard_problem": {"queued": False, "title": "", "reason": "heuristic"}}
        return fallback
    try:
        try:
            raw = llm_client.complete(prompt, max_tokens=256, temperature=0.2, timeout=timeout)
        except TypeError:
            raw = llm_client.complete(prompt, max_tokens=256, temperature=0.2)
        import re
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            j = json.loads(m.group(0))
            issues = [_norm_issue(i) for i in (j.get("issues") or [])]
            return {"issues": [i for i in issues if i],
                    "hard_problem": _norm_hard(j.get("hard_problem"))}
    except Exception as e:
        return {**fallback, "hard_problem": {**fallback["hard_problem"], "reason": str(e)[:200]}}
    return fallback


def handle_response(base: pathlib.Path, user_msg: str, assistant_final: str, tool_trace: str = "",
                    llm_client=None, timeout: int = 45):
    res = analyze(user_msg, assistant_final, tool_trace, llm_client, timeout)
    evo = base / "self_evolution"
    queue = evo / "queue"
    queue.mkdir(parents=True, exist_ok=True)
    seen = _recent_keys(base)
    fixes_log = queue / "fixes.jsonl"
    new_pending = 0
    for iss in res.get("issues", []):
        key = _issue_key(iss)
        if key in seen:
            continue  # already logged/pending/queued/decided — don't flood
        seen.add(key)
        entry = {"ts": datetime.datetime.utcnow().isoformat(), "key": key,
                 "user": user_msg[:200], "assistant": assistant_final[:500], "issue": iss}
        if iss.get("severity") in ("low", "med"):
            pending = evo / "patches" / "pending" / f"{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}.json"
            pending.parent.mkdir(parents=True, exist_ok=True)
            pending.write_text(json.dumps(entry, indent=2))
            new_pending += 1
        with open(fixes_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    _rotate(fixes_log, FIXES_RETAIN)
    hp = res.get("hard_problem") or {}
    if hp.get("queued"):
        _enqueue_hard(base, hp, user_msg, assistant_final, tool_trace)
    elog = evo / "evolution.log"
    with open(elog, "a") as f:
        f.write(json.dumps({"type": "avg_evo", "ts": datetime.datetime.utcnow().isoformat(),
                            "new_pending": new_pending, "result": res}) + "\n")
    res["new_pending"] = new_pending
    return res


def _rotate(path: pathlib.Path, keep: int) -> None:
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return
    if len(lines) > keep:
        path.write_text("\n".join(lines[-keep:]) + "\n")


def _enqueue_hard(base, hp, user_msg, assistant_final, tool_trace):
    p = base / "self_evolution" / "queue" / "hard.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text().splitlines() if p.exists() else []
    if len(lines) >= 50:
        lines = lines[1:]
        p.write_text("\n".join(lines) + ("\n" if lines else ""))
    entry = {"ts": datetime.datetime.utcnow().isoformat(), "title": hp.get("title", "untitled"),
             "reason": hp.get("reason", ""), "user": user_msg[:500],
             "assistant": assistant_final[:800], "trace": tool_trace[:800]}
    with open(p, "a") as f:
        f.write(json.dumps(entry) + "\n")
