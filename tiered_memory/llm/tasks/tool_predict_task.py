"""Task: working-set tool predictor (1B — qwen2-0_5b via llama.cpp)
Called by: tools/working_set.py predict_async — fire-and-forget per user turn.
Job: guess which tools the next turn needs so schemas arrive BEFORE the main
model asks. Best-effort: unknown names are dropped, max 3 kept. When unsure,
output fewer — a wrong guess costs tokens, a miss costs one bridge turn.
"""
PROMPT = """You predict tools. Nothing else.

USER MESSAGE:
{text}

AVAILABLE TOOL NAMES:
{names}

OUTPUT — comma-separated tool names from the list above. NOTHING else.
No explanation. Max 3. Unsure → output exactly: none

RULES:
1. Copy names EXACTLY from the list. Never invent.
2. Files/paths/code mentioned → terminal, read_file, search_files.
3. Remember/recall/about-me → memory, recall_backup.
4. Web/URLs/news → web_search, web_extract.
5. Images → vision_analyze. Schedules → cronjob_manage.
6. Vague chit-chat → none.

EXAMPLE:
USER: "read main.py and find where auth happens"
OUTPUT: read_file, search_files, terminal

FORBIDDEN: sentences, explanation, invented names, more than 3.
"""

_FALLBACK_NAMES = (
    "terminal, read_file, write_file, patch, search_files, web_search, web_extract, "
    "vision_analyze, memory, recall_backup, read_state, write_state, session_search, "
    "skill_view, skills_list, delegate_task, todo_list, clarify, cronjob_manage, "
    "browser_navigate, execute_code, text_to_speech"
)

def build_prompt(text: str, names: str = _FALLBACK_NAMES) -> str:
    return PROMPT.format(text=text[:600], names=names[:1200])
