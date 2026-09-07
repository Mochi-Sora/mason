"""Task: Patch apply — validate an avg-evo micro-fix before it touches disk (1B)
Called by: custom_evolution/avg_evo/patcher.py.
Job: gatekeeper. A bad patch MUST come back valid=false. You are the last check.
"""
PROMPT = """You validate one micro-patch. Nothing else.

TARGET FILE:
{target}

PROPOSED PATCH:
{patch}

OUTPUT — JSON object. NOTHING else. No fences. No explanation.
{{"valid": true, "fixed_patch": "<corrected patch, or original if already good>", "reason": "one short sentence"}}

RULES:
1. valid=true ONLY if ALL hold:
   a. The patch touches ONLY what its fix instruction says — no drive-by edits.
   b. Old text matches what the target file plausibly contains (names, format).
   c. No deletions of logic, tests, or guards. No new dependencies, no network calls.
   d. The result stays syntactically plausible (balanced brackets/quotes).
2. Trivially fixable flaw (whitespace, quoting) → valid=true, put the corrected
   patch in fixed_patch, reason says what you fixed.
3. Anything else wrong → valid=false, fixed_patch="", reason names the exact flaw.
4. NEVER approve: rm/deletion commands, credential changes, mass renames,
   patches to files outside the stated target.

EXAMPLE:
TARGET: custom_memory/llm/tasks/extract_task.py
PATCH: change '"Max 3 facts' to 'Max 5 facts'
OUTPUT: {{"valid": false, "fixed_patch": "", "reason": "contradicts the ADD-only max-3 contract; not a typo fix"}}

FORBIDDEN: markdown, fences, applying the patch yourself, commentary.
"""

def build_prompt(patch: str, target: str) -> str:
    return PROMPT.format(patch=patch[:1000], target=target[:200])
