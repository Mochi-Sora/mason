"""Task: mem0-style ADD-only extraction (1B — qwen2-0_5b via llama.cpp)
Called by: custom_memory/short_term/manager.py — every remember.
Why ADD-only (mem0 2026): never rewrite history; dedup happens at recall.
"""
PROMPT = """You extract durable facts. Nothing else.

INPUT — one chat message:
{text}

OUTPUT — a JSON array of strings. NOTHING else. No fences. No explanation.
["fact one", "fact two"]

RULES:
1. ADD-only: extract new facts. Never update, merge, or delete old ones.
2. Each fact is ONE self-contained sentence WITH the person/thing named.
   Good: "Marco prefers dark mode in every editor".
   Bad: "prefers dark mode" (who?).
3. Keep: preferences, decisions, commitments, relationships, plans.
4. Drop: greetings, jokes, chit-chat, questions with no answer.
5. Max 3 facts. If nothing durable, output exactly: []

EXAMPLE:
INPUT: I love potatoes and badminton, remind me Friday to restring my racket
OUTPUT: ["User loves potatoes", "User plays badminton", "User must restring badminton racket by Friday"]

FORBIDDEN: markdown, ```json fences, commentary, more than 3 facts.
"""

def build_prompt(text: str) -> str:
    return PROMPT.format(text=text[:800])
