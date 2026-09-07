"""Aux task: triage_specifier — default to local 1B (llama.cpp)
Called by: agent/auxiliary_client.py get_text_auxiliary_client(task="triage_specifier").
Route: provider=local, base_url=http://127.0.0.1:8080, model=qwen2-0_5b.
Job: turn a vague request into a sharp spec the main model can execute blind.
"""
TASK = "triage_specifier"
PROMPT_HEADER = "You are the triage_specifier auxiliary."
DEFAULTS = {"provider": "local", "base_url": "http://127.0.0.1:8080", "model": "qwen2-0_5b-instruct", "timeout": 30}
PROMPT = """You write a work spec. Nothing else.

VAGUE REQUEST:
{request}

OUTPUT — JSON object. NOTHING else. No fences. No explanation.
{{"goal": "one sentence", "inputs": ["known fact 1"], "wanted_output": "what done looks like", "constraints": ["limit 1"], "missing": ["info needed, or empty"]}}

RULES:
1. goal: the single concrete outcome, verb first ("Fix…", "Draft…", "Compare…").
2. inputs: ONLY facts stated in the request. Never assume.
3. missing: questions that block execution. Empty list if none.
4. Keep every value under 25 words.

EXAMPLE:
REQUEST: "make the tests faster somehow"
OUTPUT: {{"goal": "Reduce test suite runtime", "inputs": ["test suite exists", "currently slow"], "wanted_output": "Faster suite, same coverage", "constraints": ["no coverage loss"], "missing": ["which suite", "current runtime", "target runtime"]}}

FORBIDDEN: markdown, fences, solving the task (spec ONLY), invented facts.
"""

def build_prompt(request: str) -> str:
    return PROMPT.format(request=request[:800])
