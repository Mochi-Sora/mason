"""Task: Nightly-Dream-cycle — lightweight sweep (1B — qwen2-0_5b via llama.cpp)
Called by: self_evolution/nightly/sweep.py — every night 02:00, always runs.
Job: close out the day WITHOUT the main model: dedupe learnings, bank patch
proposals, list gaps. Cheap, factual, boring — that is the point.
"""
PROMPT = """You close out the day. Nothing else.

TODAY'S SHORT-TERM BULLETS:
{bullets}

FIX LOG (avg-evo low/med, not yet applied):
{fixes}

TOOL ERRORS TODAY:
{errors}

OUTPUT — markdown report, EXACTLY these 4 sections, under 300 words total.
No extra sections. No preamble.

## Lightweight Evolution Report — {date}
- Summary: <exactly 2 sentences: what happened today, what state things are in>
- Learnings (deduped, with provenance in parens):
  - <learning 1 (source)>
- Patch proposals (one line each: file + change):
  - <path>: <change>
- Gaps (memory still missing):
  - <gap 1>

RULES:
1. Dedupe learnings that say the same thing — keep the clearest, cite all sources.
2. Patch proposals must name a REAL file from the fix log. No invented paths.
3. Gaps = questions today raised but never answered. Max 3.
4. "Nothing to report" sections get one line: "- none." Never leave a section empty.
5. Under 300 words. Count roughly: if in doubt, cut words.

FORBIDDEN: extra sections, prose essays, invented files, over 300 words.
"""

def build_prompt(bullets: str, fixes: str, errors: str, date: str) -> str:
    return PROMPT.format(bullets=bullets[:3000], fixes=fixes[:1200], errors=errors[:1200], date=date)
