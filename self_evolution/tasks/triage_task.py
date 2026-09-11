"""Task: Tool error triage — classify if an error needs the hard queue (1B)
Called by: analyzer when tool_trace contains an error.
Job: retry-fast things stay local, real problems get queued. Decide in one pass.
"""
PROMPT = """You triage one tool error. Nothing else.

ERROR:
{error}

OUTPUT — JSON object. NOTHING else. No fences. No explanation.
{{"severity": "low|med|high", "retry": true, "queue": false, "fix": "one-line instruction"}}

RULES:
1. retry=true: transient or self-fixable — timeout, rate limit, bad quoting,
   missing dir that can be created, typo'd path. fix = the exact retry step.
2. queue=true: needs real reasoning — auth broken, API changed, data corrupt,
   repeated failure. severity=high then.
3. severity: low = cosmetic warning; med = one feature failed, workaround exists;
   high = task blocked or unsafe to retry.
4. retry=true AND queue=true is allowed (retry now, queue the root cause).
5. fix is ALWAYS concrete: "retry with quotes escaped" — never "check error".

EXAMPLE:
ERROR: "terminal: cd /nonexistent: No such file or directory"
OUTPUT: {{"severity": "med", "retry": true, "queue": false, "fix": "create /nonexistent first with mkdir -p, then retry"}}

FORBIDDEN: markdown, fences, commentary, vague fixes.
"""

def build_prompt(error: str) -> str:
    return PROMPT.format(error=error[:800])
