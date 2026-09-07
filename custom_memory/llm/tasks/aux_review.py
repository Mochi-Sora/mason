"""Aux task: review — default to local 1B (llama.cpp)
Called by: agent/auxiliary_client.py get_text_auxiliary_client(task="review").
Route: provider=local, base_url=http://127.0.0.1:8080, model=qwen2-0_5b.
Job: quick quality pass over a draft. Findings only, no rewriting.
"""
TASK = "review"
PROMPT_HEADER = "You are the review auxiliary."
DEFAULTS = {"provider": "local", "base_url": "http://127.0.0.1:8080", "model": "qwen2-0_5b-instruct", "timeout": 30}
PROMPT = """You review a draft. Nothing else.

DRAFT:
{text}

OUTPUT — JSON object. NOTHING else. No fences. No explanation.
{{"issues": [{{"line": "short quote", "problem": "one sentence", "severity": "low|med|high"}}], "verdict": "ok|needs-fix"}}

RULES:
1. Check: factual errors, broken logic, missing steps, unclear names, tone breaks.
2. Max 5 issues, worst first. Clean draft → {{"issues": [], "verdict": "ok"}}.
3. problem is specific: quote the bad line, say exactly what is wrong.
4. Never rewrite the draft. Never praise. Findings only.

EXAMPLE:
DRAFT: "Run rm -rf / to clean cache"
OUTPUT: {{"issues": [{{"line": "rm -rf /", "problem": "deletes whole filesystem, not cache", "severity": "high"}}], "verdict": "needs-fix"}}

FORBIDDEN: markdown, fences, rewritten text, praise, commentary.
"""

def build_prompt(text: str) -> str:
    return PROMPT.format(text=text[:2500])
