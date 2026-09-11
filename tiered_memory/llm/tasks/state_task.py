"""Task: State history — decide what stays in state.md (1B)
Called by: sessions/container.py update_state (+ prompt_builder context).
Job: compress ONE turn into the tiny state. The main model sees ONLY this
file, so every bullet must earn its place. Under 800 chars, always.
"""
PROMPT = """You maintain state.md — the main model's tiny working memory. Nothing else.

CURRENT STATE:
{state}

NEW TURN:
User: {user_msg}
Assistant: {assistant_msg}

OUTPUT — the FULL new state.md. Bullets only. Under 800 characters total.
No fences. No explanation. No header.

RULES:
1. KEEP: active goal, decisions made, named entities, open todos, blockers.
2. DROP: greetings, chit-chat, verbatim tool output (backup.md already has it),
   anything unchanged from CURRENT STATE (don't duplicate).
3. Each bullet ≤ 100 chars. Max 8 bullets. Newest info wins on conflict.
4. If the turn adds nothing durable, output CURRENT STATE unchanged.

EXAMPLE:
CURRENT STATE:
- Goal: plan Friday release
NEW TURN: User: "release moved to Monday" / Assistant: "noted, checklist shifted"
OUTPUT:
- Goal: plan Monday release (moved from Friday)
- Open: shift release checklist to Monday

FORBIDDEN: prose paragraphs, headers, fences, over 800 chars, tool output dumps.
"""

def build_prompt(state: str, user_msg: str, assistant_msg: str) -> str:
    return PROMPT.format(state=state[:1000], user_msg=user_msg[:400], assistant_msg=assistant_msg[:600])
