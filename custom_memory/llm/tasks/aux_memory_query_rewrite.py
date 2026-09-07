"""Aux task: memory_query_rewrite — default to local 1B (llama.cpp)
Called by: agent/auxiliary_client.py get_text_auxiliary_client(task="memory_query_rewrite").
Route: provider=local, base_url=http://127.0.0.1:8080, model=qwen2-0_5b.
Job: turn a natural question into FTS5-friendly keywords for backup/memory search.
"""
TASK = "memory_query_rewrite"
PROMPT_HEADER = "You are the memory_query_rewrite auxiliary."
DEFAULTS = {"provider": "local", "base_url": "http://127.0.0.1:8080", "model": "qwen2-0_5b-instruct", "timeout": 30}
PROMPT = """You rewrite a question into search keywords. Nothing else.

QUESTION:
{question}

OUTPUT — ONE line: space-separated keywords. NOTHING else. No quotes. No explanation.

RULES:
1. Keep nouns, verbs, names. Drop: who/what/when/why/how, please, articles, punctuation.
2. Expand with ONE synonym for the key term when obvious (theme → theme dark mode).
3. Max 8 keywords. Order: most distinctive first.
4. Never answer the question. Only rewrite it.

EXAMPLE:
QUESTION: What editor theme does Marco like?
OUTPUT: Marco editor theme dark mode preference

FORBIDDEN: sentences, quotes, answering, more than 8 words.
"""

def build_prompt(question: str) -> str:
    return PROMPT.format(question=question[:400])
