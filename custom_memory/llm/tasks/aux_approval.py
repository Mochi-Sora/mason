"""Aux task: approval — default to local 1B (llama.cpp)
Called by: agent/auxiliary_client.py get_text_auxiliary_client(task="approval").
Route: provider=local, base_url=http://127.0.0.1:8080, model=qwen2-0_5b.
Job: judge ONE proposed action against a policy. Small model, strict format.
"""
TASK = "approval"
PROMPT_HEADER = "You are the approval auxiliary."
DEFAULTS = {"provider": "local", "base_url": "http://127.0.0.1:8080", "model": "qwen2-0_5b-instruct", "timeout": 30}
PROMPT = """You judge one action. Nothing else.

ACTION:
{action}

POLICY:
{policy}

OUTPUT — JSON object. NOTHING else. No fences. No explanation.
{{"approved": true, "reason": "one short sentence"}}

RULES:
1. approved=true ONLY if the action clearly satisfies every policy line.
2. Any doubt, any missing info → approved=false, reason says what is missing.
3. reason ≤ 20 words. Never approve destructive actions without explicit policy cover.

EXAMPLE:
ACTION: delete /tmp/cache
POLICY: temp files under /tmp may be deleted
OUTPUT: {{"approved": true, "reason": "tmp cache deletion is explicitly allowed"}}

FORBIDDEN: markdown, fences, commentary, approving on assumptions.
"""

def build_prompt(action: str, policy: str = "Standard safety policy: no destructive, irreversible, or external actions without explicit user approval.") -> str:
    return PROMPT.format(action=action[:800], policy=policy[:800])
