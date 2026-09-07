"""Promoter: expired short-term (older than 7d) → long-term via 1B LLM"""
import json, pathlib
from custom_memory.llm.tasks.promoter_task import build_prompt

def evaluate(content: str, filename: str, llm_client=None) -> dict:
    if llm_client is None:
        bullets = [l for l in content.splitlines() if l.strip().startswith("-")]
        if len(bullets) >= 2:
            return {"promote": True, "facts": [b.lstrip("- ").split("—",1)[-1].strip() for b in bullets[:3]], "reason": "heuristic: multiple bullets"}
        return {"promote": False, "facts": [], "reason": "heuristic: too few bullets"}
    prompt = build_prompt(content, filename)
    try:
        resp = llm_client.complete(prompt, max_tokens=256, temperature=0.2)
        import re
        m = re.search(r"\{.*\}", resp, re.S)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        return {"promote": False, "facts": [], "reason": f"llm error: {e}"}
    return {"promote": False, "facts": [], "reason": "no JSON"}

def promote_file(base: pathlib.Path, filename: str, long_term_store, llm_client=None):
    p = base / "short_term_memories" / filename
    if not p.exists():
        return {"promote": False, "reason": "file not found"}
    content = p.read_text()
    res = evaluate(content, filename, llm_client)
    if res.get("promote") and res.get("facts"):
        for fact in res["facts"]:
            long_term_store.remember(fact, provenance=f"short-term:{filename}")
    return res
