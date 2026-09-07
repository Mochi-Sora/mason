"""Task: Session-close promotion — backup → short-term (1B)
Called by: sessions/manager.py on_session_close.
Job: last chance to rescue durable facts before the session folder is purged.
Max 5. When unsure, leave it out — short-term is only 7 x 3000 chars.
"""
PROMPT = """You rescue facts before this session is purged. Nothing else.

INPUT — indexed backup chunks from the closing session:
{backup}

OUTPUT — a JSON array of strings. NOTHING else. No fences. No explanation.
["fact one", "fact two"]

RULES:
1. Max 5 facts. Each ONE self-contained sentence WITH the entity named.
2. Keep: preferences, learnings, relationships, commitments, decisions.
3. Drop: tool verbatim, error logs, chit-chat, anything already obvious.
4. Nothing durable → output exactly: []

EXAMPLE:
INPUT: "fixed test_auth by mocking Path.home ... Marco: I hate morning meetings ... lol ok"
OUTPUT: ["test_auth fixed by mocking Path.home", "Marco hates morning meetings"]

FORBIDDEN: markdown, ```json fences, commentary, more than 5 facts, logs.
"""

def build_prompt(backup: str) -> str:
    return PROMPT.format(backup=backup[:4000])
