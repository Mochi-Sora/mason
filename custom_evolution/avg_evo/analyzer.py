"""Avg-evo analyzer — 1B per-response fix + queue"""
import json, pathlib, datetime
from custom_evolution.tasks.avg_evo_task import build_prompt

def analyze(user_msg: str, assistant_final: str, tool_trace: str = "", llm_client=None) -> dict:
    prompt = build_prompt(user_msg, assistant_final, tool_trace)
    fallback = {"issues": [], "hard_problem": {"queued": False, "title": "", "reason": "llm unavailable"}}
    if llm_client is None:
        if "error" in assistant_final.lower() or "failed" in assistant_final.lower():
            return {"issues": [{"type":"error","severity":"med","fix":"retry tool or clarify"}], "hard_problem":{"queued": False,"title":"","reason":"heuristic"}}
        return fallback
    try:
        raw = llm_client.complete(prompt, max_tokens=256, temperature=0.2)
        import re
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            j = json.loads(m.group(0))
            j.setdefault("issues",[])
            j.setdefault("hard_problem", {"queued": False})
            return j
    except Exception as e:
        return {**fallback, "reason": str(e)}
    return fallback

def handle_response(base: pathlib.Path, user_msg: str, assistant_final: str, tool_trace: str = "", llm_client=None):
    res = analyze(user_msg, assistant_final, tool_trace, llm_client)
    fixes_log = base / "custom_evolution" / "queue" / "fixes.jsonl"
    fixes_log.parent.mkdir(parents=True, exist_ok=True)
    hard_q = base / "custom_evolution" / "queue" / "hard.jsonl"
    for iss in res.get("issues",[]):
        entry = {"ts": datetime.datetime.utcnow().isoformat(), "user": user_msg[:200], "assistant": assistant_final[:500], "issue": iss}
        if iss.get("severity") in ("low","med"):
            pending = base / "custom_evolution" / "patches" / "pending" / f"{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}.json"
            pending.parent.mkdir(parents=True, exist_ok=True)
            pending.write_text(json.dumps(entry, indent=2))
        with open(fixes_log, "a") as f:
            f.write(json.dumps(entry)+"\n")
    hp = res.get("hard_problem") or {}
    if hp.get("queued"):
        _enqueue_hard(base, hp, user_msg, assistant_final, tool_trace)
    elog = base / "custom_evolution" / "evolution.log"
    with open(elog, "a") as f:
        f.write(json.dumps({"type":"avg_evo","ts":datetime.datetime.utcnow().isoformat(),"result":res})+"\n")
    return res

def _enqueue_hard(base, hp, user_msg, assistant_final, tool_trace):
    p = base / "custom_evolution" / "queue" / "hard.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text().splitlines() if p.exists() else []
    if len(lines) >= 50:
        lines = lines[1:]
        p.write_text("\n".join(lines) + ("\n" if lines else ""))
    entry = {"ts": datetime.datetime.utcnow().isoformat(), "title": hp.get("title","untitled"), "reason": hp.get("reason",""), "user": user_msg[:500], "assistant": assistant_final[:800], "trace": tool_trace[:800]}
    with open(p, "a") as f:
        f.write(json.dumps(entry)+"\n")
