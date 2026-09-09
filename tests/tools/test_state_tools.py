"""State-tool session resolution: agent-level calls must serve the LIVE session.

Regression: the INLINE_TOOL_EXECUTORS entries for read_state / write_state /
recall_backup hardcoded session_id="default", so a recall on any real session
(sessions are timestamped ids like 20260909_151559_2bac0f, never "default")
silently returned zero hits while the transcript kept appending to the real
container. The executors now thread the agent's session id, mirroring
append_backup's keying. Inline executors return the module function's value
(already a dict) — the caller serializes.
"""
from agent.inline_tool_executors import INLINE_TOOL_EXECUTORS, InlineToolContext
from sessions.container import append_backup, get_sessions_root, init_session
from tools import state_tools


def _seed(session_id: str, marker: str) -> None:
    init_session(session_id)
    append_backup(session_id, "user", marker + " needle-in-this-haystack")


def _ctx() -> InlineToolContext:
    return InlineToolContext(effective_task_id="")


class _FakeAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id


def test_recall_backup_targets_live_agent_session():
    _seed("sess-live", "alpha")
    out = INLINE_TOOL_EXECUTORS["recall_backup"](
        _FakeAgent("sess-live"), {"query": "needle"}, _ctx())
    assert out["total"] >= 1
    assert any("alpha needle-in-this-haystack" in c["chunk"] for c in out["results"])


def test_explicit_session_id_overrides_live_agent_session():
    _seed("sess-other", "alpha")
    _seed("sess-live", "beta")
    out = INLINE_TOOL_EXECUTORS["recall_backup"](
        _FakeAgent("sess-live"), {"query": "needle", "session_id": "sess-other"}, _ctx())
    chunks = "\n".join(c["chunk"] for c in out["results"])
    assert "alpha needle-in-this-haystack" in chunks
    assert "beta needle-in-this-haystack" not in chunks


def test_write_state_and_read_state_target_live_agent_session():
    init_session("sess-live")
    INLINE_TOOL_EXECUTORS["write_state"](
        _FakeAgent("sess-live"), {"content": "# State\n- keep going"}, _ctx())
    stored = (get_sessions_root() / "sess-live" / "state.md").read_text()
    assert "keep going" in stored
    # module-level fallback honours current_session_id too
    assert "keep going" in state_tools.read_state(current_session_id="sess-live")


def test_legacy_default_container_still_reachable_when_no_session():
    init_session("default")
    _seed("default", "legacy")
    out = INLINE_TOOL_EXECUTORS["recall_backup"](
        _FakeAgent(""), {"query": "needle"}, _ctx())
    assert any("legacy needle-in-this-haystack" in c["chunk"] for c in out["results"])
