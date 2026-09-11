"""Task: tool-summary maintainer (1B — qwen2-0_5b via llama.cpp)
Called by: nightly sweep (refresh pass) + scripts/gen_tool_index.py seeding.
Job: ONE sharp line per tool so the model picks right from the name list.
A vague summary causes wrong picks; a wrong pick costs a bridge turn.
"""
PROMPT = """You write a tool summary. Nothing else.

TOOL NAME:
{name}

FULL DESCRIPTION:
{description}

OUTPUT — ONE line: "<name>: <summary>". NOTHING else. No quotes. No period.

RULES:
1. Summary ≤ 12 words, verb first: "run shell commands", "search file contents".
2. Disambiguate from neighbors: if SIBLINGS are listed, say how THIS one differs.
3. Name the object it acts on (files, web, sessions, tools).
4. Copy the tool name EXACTLY.

SIBLINGS (do not describe these, only differ from them):
{siblings}

EXAMPLE:
TOOL NAME: recall_backup
FULL DESCRIPTION: Search the session's indexed backup.md file with FTS5...
SIBLINGS: read_state (tiny state.md), memory (long-term facts), session_search (past sessions)
OUTPUT: recall_backup: search this session's indexed backup file

FORBIDDEN: sentences, quotes, periods, describing siblings, over 12 words.
"""

def build_prompt(name: str, description: str, siblings: str = "") -> str:
    return PROMPT.format(name=name[:80], description=description[:800], siblings=siblings[:400])
