"""Aux task: title_generation — default to local 1B (llama.cpp)
Called by: agent/auxiliary_client.py get_text_auxiliary_client(task="title_generation").
Route: provider=local, base_url=http://127.0.0.1:8080, model=qwen2-0_5b.
Job: ONE short title for a session/text. 8 words max. That is the whole job.
"""
TASK = "title_generation"
PROMPT_HEADER = "You are the title_generation auxiliary."
DEFAULTS = {"provider": "local", "base_url": "http://127.0.0.1:8080", "model": "qwen2-0_5b-instruct", "timeout": 30}
PROMPT = """You write one title. Nothing else.

TEXT:
{text}

OUTPUT — the title alone. One line. Max 8 words. No quotes. No period. No explanation.

RULES:
1. Name the topic + the action: "Fix auth mock", "Plan Monday release".
2. No filler words (discussion about, some thoughts on).
3. Never output more than one line.

EXAMPLE:
TEXT: "debugging why test_auth fails on CI, mocking Path.home fixed it"
OUTPUT: Fix test_auth CI failure

FORBIDDEN: quotes, periods, second lines, explanation.
"""

def build_prompt(text: str) -> str:
    return PROMPT.format(text=text[:800])
