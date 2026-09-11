"""Task: Long-term synthesize — answer with citations (1B)
Called by: tiered_memory/long_term/synthesize.py.
Job: answer STRICTLY from the given facts. Never invent. Say what is missing.
"""
PROMPT = """You answer only from the facts below. Nothing else.

FACTS (each ends with its source id in [brackets]):
{facts}

QUESTION:
{question}

OUTPUT — plain sentences. Every claim ends with its [source id].
If the facts cannot answer, output exactly one line:
GAP: <what is missing>

RULES:
1. Use ONLY the facts above. No outside knowledge. No guessing.
2. Copy each claim's [source id] right after the claim.
3. Short: 1-3 sentences unless the question needs more.
4. Never output "as an AI". Never explain your process.

EXAMPLE:
FACTS: Marco prefers dark mode [f3]. Friday release decided [f7].
QUESTION: What editor theme does Marco like?
OUTPUT: Marco prefers dark mode [f3].

FORBIDDEN: uncited claims, outside knowledge, preamble.
"""

def build_prompt(facts: str, question: str) -> str:
    return PROMPT.format(facts=facts[:2500], question=question[:500])
