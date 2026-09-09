"""Session lifecycle: close → promote → purge"""
import pathlib, json
from .container import get_sessions_root, purge_session, recall_backup

def on_session_close(session_id: str, base: pathlib.Path | None = None):
    base = pathlib.Path(base) if base else pathlib.Path(__file__).parent.parent
    # 1) read backup via indexed recall (not raw 10M)
    # Use llm to extract facts
    try:
        from custom_memory.llm.client import LlamaClient
        from custom_memory.llm.tasks.session_promote_task import build_prompt
        d = get_sessions_root() / session_id
        backup = (d / "backup.md").read_text() if (d / "backup.md").exists() else ""
        if not backup.strip():
            # backup empty but state.db may have real transcript — promote from there instead of dropping
            try:
                from mason_state import SessionDB
                db = SessionDB()
                msgs = db.get_messages(session_id) or []
                if msgs:
                    # synthesize backup from state.db transcript for promotion
                    backup = "\n".join(f"{m.get('role','')}: {str(m.get('content',''))[:500]}" for m in msgs[-20:])
                db.close()
            except Exception:
                pass
            if not backup.strip():
                purge_session(session_id)
                return {"promoted": []}
        llm = LlamaClient()
        prompt = build_prompt(backup)
        raw = llm.complete(prompt, max_tokens=300)
        import re
        m = re.search(r"\[.*\]", raw, re.S)
        facts = json.loads(m.group(0)) if m else []
    except Exception:
        facts = []
    _backup_for_fallback = locals().get("backup", "")
    if not facts and isinstance(_backup_for_fallback, str) and _backup_for_fallback.strip():
        # LLM dormant (no server/GGUF) or returned no JSON — heuristic so close still promotes
        try:
            from custom_memory.short_term.manager import _extract_facts_mem0
            facts = _extract_facts_mem0(_backup_for_fallback, llm_client=None)
        except Exception:
            facts = []
    # 2) promote to short-term (intact)
    from custom_memory.short_term.manager import remember as st_remember
    for f in facts[:5]:
        try:
            st_remember(base, f, llm_client=None)  # heuristic fallback ok at close
        except Exception:
            pass
    # 3) purge session container — no exceptions, everything deleted
    purge_session(session_id)
    # also sweep any other empty zombies (the 6 empty shells) so they don't accumulate
    try:
        from .container import purge_empty_sessions
        purge_empty_sessions()
    except Exception:
        pass
    return {"promoted": facts, "purged": session_id}
