"""synthesize: Gbrain-style answer with citations (via 1B or fallback)"""
from .store import recall as lt_recall
from custom_memory.llm.tasks.synthesize_task import build_prompt

def synthesize(base, question: str, llm_client=None, limit=5) -> str:
    res = lt_recall(base, query=question, limit=limit)
    facts = res.get("facts",[])
    if not facts:
        return "I don't know yet — no long-term memory matches. (gap: no facts for this query)"
    ctx = "\n".join(f"- {f['fact']} [{f['provenance']}]" for f in facts)
    if llm_client:
        prompt = build_prompt(ctx, question)
        try:
            return llm_client.complete(prompt, max_tokens=256)
        except Exception:
            pass
    return "Based on long-term memory:\n" + ctx + "\n"
