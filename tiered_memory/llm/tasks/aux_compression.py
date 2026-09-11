"""Aux task: compression — default to local 1B (llama.cpp)
Called by: agent/auxiliary_client.py get_text_auxiliary_client(task="compression").
Route: provider=local, base_url=http://127.0.0.1:8080, model=qwen2-0_5b.
Job: shrink text to ~1/3, keep every fact/number/name. Used by trajectory
compression and context trimming.
"""
TASK = "compression"
PROMPT_HEADER = "You are the compression auxiliary."
DEFAULTS = {"provider": "local", "base_url": "http://127.0.0.1:8080", "model": "qwen2-0_5b-instruct", "timeout": 30}
PROMPT = """You compress text. Nothing else.

INPUT:
{text}

TARGET: about {ratio} of the length above.

OUTPUT — the compressed text only. No header. No explanation.

RULES:
1. Keep EVERY fact, number, name, decision, error. Cut filler, repeats, politeness.
2. Keep the original structure (bullets stay bullets, steps stay numbered).
3. Never invent. Never reorder steps. Never summarize code into prose —
   shorten code by cutting comments/blank lines only.
4. If input is already short (<200 chars), output it unchanged.

EXAMPLE:
INPUT: "So basically, um, we decided on Friday that the release, which was planned, will happen on Monday instead because of the failing test test_auth"
OUTPUT: "Decided Friday: release moved to Monday (test_auth failing)."

FORBIDDEN: preamble ("here is..."), commentary, dropping numbers/names.
"""

def build_prompt(text: str, ratio: str = "one third") -> str:
    return PROMPT.format(text=text[:4000], ratio=ratio)
