"""Task: Backup watcher — 85% emergency summary (1B)
Called by: sessions/container.py _trigger_summary when backup.md exceeds 8.5M chars.
Job: shrink the OLDEST 30% into bullets. Facts survive, filler dies.
"""
PROMPT = """You compress old backup. Nothing else.

INPUT — oldest 30% chunk of backup.md:
{chunk}

OUTPUT — markdown bullets only, under 600 characters total. No header. No fences.
- fact one
- fact two

RULES:
1. Preserve: facts, named entities, decisions, and their provenance in parens.
   Good: "- Friday release decided (standup Sep 7)".
2. Delete: greetings, repeated tool output, stack traces, chit-chat.
3. Each bullet ≤ 120 chars. Few bullets beat many words.
4. Never invent. If a line is unclear, drop it.

EXAMPLE:
INPUT: "lol hi ... decided Monday release (Marco) ... Traceback ... 200 lines ... Marco hates 9am meetings"
OUTPUT:
- Monday release decided (Marco)
- Marco hates 9am meetings

FORBIDDEN: headers, fences, prose, stack traces, over 600 chars.
"""

def build_prompt(chunk: str) -> str:
    return PROMPT.format(chunk=chunk[:5000])
