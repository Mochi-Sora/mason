"""Session lifecycle: close → promote → purge"""
import pathlib, json
from .container import ROOT, purge_session, recall_backup

def on_session_close(session_id: str, base: pathlib.Path | None = None):
    base = pathlib.Path(base) if base else pathlib.Path(__file__).parent.parent
    # 1) read backup via indexed recall (not raw 10M)
    # Use llm to extract facts
    try:
        from custom_memory.llm.client import LlamaClient
        from custom_memory.llm.tasks.session_promote_task import build_prompt
        d = ROOT / session_id
        backup = (d / "backup.md").read_text() if (d / "backup.md").exists() else ""
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
    # 2) promote to short-term (intact)
    from custom_memory.short_term.manager import remember as st_remember
    for f in facts[:5]:
        try:
            st_remember(base, f, llm_client=None)  # heuristic fallback ok at close
        except Exception:
            pass
    # 3) purge session container — no exceptions, everything deleted
    purge_session(session_id)
    return {"promoted": facts, "purged": session_id}
