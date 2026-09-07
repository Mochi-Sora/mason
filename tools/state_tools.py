"""State history tools — read_state / write_state / recall_backup.

Registered in the file registry (schemas reach the model; deferrable behind the
bridge like every other tool) AND in agent INLINE_TOOL_EXECUTORS (fast path).
Registry is the source of truth for schemas; keep both in sync.
"""
import json
import pathlib

from sessions.container import recall_backup as _recall, ROOT
from tools.registry import registry  # noqa: E402  (registration at import time)


def read_state(session_id: str = "default") -> str:
    p = pathlib.Path("sessions") / session_id / "state.md"
    # Try both CWD-relative and repo-root
    for cand in [p, pathlib.Path(__file__).parent.parent / p]:
        if cand.exists():
            return cand.read_text()[:2000]
    return "(no state for session {})".format(session_id)


def write_state(content: str, session_id: str = "default") -> dict:
    from sessions.container import update_state
    update_state(session_id, content)
    return {"status": "updated", "session_id": session_id, "chars": len(content)}


def recall_backup(query: str, session_id: str = "default", budget_tokens: int = 2000, limit: int = 5) -> dict:
    from sessions.container import recall_backup as _rb
    return _rb(session_id, query, budget_tokens=budget_tokens, limit=limit)


def _sid(args: dict, kw: dict) -> str:
    return str(args.get("session_id") or kw.get("current_session_id") or "default")


def _h_read(args: dict, **kw: object) -> str:
    return json.dumps({"state": read_state(_sid(args, kw))})


def _h_write(args: dict, **kw: object) -> str:
    return json.dumps(write_state(str(args.get("content") or ""), _sid(args, kw)))


def _h_recall(args: dict, **kw: object) -> str:
    try:
        budget = int(args.get("budget_tokens", 2000))
    except (TypeError, ValueError):
        budget = 2000
    try:
        limit = int(args.get("limit", 5))
    except (TypeError, ValueError):
        limit = 5
    return json.dumps(recall_backup(str(args.get("query") or ""), _sid(args, kw),
                                    budget_tokens=budget, limit=limit))


registry.register(
    name="read_state", toolset="state",
    schema={"name": "read_state",
            "description": "Read the session's tiny state.md working memory (what the main model remembers).",
            "parameters": {"type": "object",
                           "properties": {"session_id": {"type": "string", "description": "Session id."}},
                           "required": []}},
    handler=_h_read)

registry.register(
    name="write_state", toolset="state",
    schema={"name": "write_state",
            "description": "Rewrite the session's tiny state.md (under 800 chars, bullets only).",
            "parameters": {"type": "object",
                           "properties": {"content": {"type": "string", "description": "Full new state.md."},
                                          "session_id": {"type": "string", "description": "Session id."}},
                           "required": ["content"]}},
    handler=_h_write)

registry.register(
    name="recall_backup", toolset="state",
    schema={"name": "recall_backup",
            "description": "Search the session's indexed backup.md file (FTS5) for past context.",
            "parameters": {"type": "object",
                           "properties": {"query": {"type": "string", "description": "Search keywords."},
                                          "session_id": {"type": "string", "description": "Session id."},
                                          "budget_tokens": {"type": "integer", "description": "Token budget, default 2000."},
                                          "limit": {"type": "integer", "description": "Max chunks, default 5."}},
                           "required": ["query"]}},
    handler=_h_recall)
