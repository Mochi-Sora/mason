"""Task: Memory recall — hybrid search reranking (1B)
Called by: tiered_memory/long_term/store.py when a query needs rerank.
Caller contract: every fact line starts with "[id] " (e.g. "[f12] Marco ...").
Job: order best-first. Nothing else.
"""
PROMPT = """You rerank facts. Nothing else.

QUERY:
{query}

FACTS (one per line, each starting with [id]):
{facts}

OUTPUT — JSON object. NOTHING else. No fences. No explanation.
{{"ranked_ids": ["f12", "f3"], "reason": "one short sentence"}}

RULES:
1. ranked_ids lists the [id]s best-first, most relevant to QUERY on top.
2. Include ONLY ids that help answer the query. Drop the rest.
3. Max 5 ids. Empty query match → {{"ranked_ids": [], "reason": "no relevant facts"}}.
4. Copy ids EXACTLY as written, brackets excluded: "[f12]" → "f12".

EXAMPLE:
QUERY: editor theme?
FACTS:
[f3] Marco prefers dark mode
[f9] Alice owes security review
OUTPUT: {{"ranked_ids": ["f3"], "reason": "only f3 is about themes"}}

FORBIDDEN: markdown, ```json fences, inventing ids, commentary.
"""

def build_prompt(query: str, facts: str) -> str:
    return PROMPT.format(query=query[:300], facts=facts[:2000])
