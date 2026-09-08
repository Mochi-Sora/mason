#!/usr/bin/env python3
"""stdio JSON-RPC bridge: Mason TUI (node/Ink) <-> live agent loop.

Protocol — one JSON object per line, responses carry the request id:
  -> {"id": 1, "op": "health"}
  <- {"id": 1, "ok": true, "model": "...", "session": "..."}
  -> {"id": 2, "op": "chat", "session_id": "tui-1", "message": "hi"}
  <- {"id": 2, "ok": true, "reply": "..."}
  -> {"id": 3, "op": "close", "session_id": "tui-1"}   # promote + purge session
  <- {"id": 3, "ok": true, "closed": true}

One cached AIAgent per session_id (warm tools + memory persist across turns).
Model/base_url/api_key from MASON_MODEL / MASON_BASE_URL / MASON_API_KEY env,
else the agent's own config resolution. MASON_MAX_TURNS caps a single message
(default 30) so a runaway can't burn API from the TUI.

All agent stdout chatter is redirected to stderr — stdout is the protocol.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

_AGENTS: dict = {}
_TURNS: dict = {}  # session_id -> {"thread": Thread}
_WRITE_LOCK = None


def _lock():
    global _WRITE_LOCK
    if _WRITE_LOCK is None:
        import threading
        _WRITE_LOCK = threading.Lock()
    return _WRITE_LOCK


def _emit(obj: dict) -> None:
    import threading as _t
    with _lock():
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _assert_repo_import() -> None:
    """Refuse to run against a stale site-packages install instead of this tree."""
    import run_agent as _ra
    here = os.path.join(REPO, "run_agent.py")
    if os.path.abspath(getattr(_ra, "__file__", "")) != os.path.abspath(here):
        raise RuntimeError(f"bridge imported run_agent from {_ra.__file__}, not {here}")


def _agent_for(session_id: str):
    if session_id in _AGENTS:
        return _AGENTS[session_id]
    from run_agent import AIAgent
    kwargs: dict = {"session_id": session_id, "platform": "cli", "quiet_mode": True}
    if os.environ.get("MASON_PROVIDER"):
        kwargs["provider"] = os.environ["MASON_PROVIDER"]
    if os.environ.get("MASON_MODEL"):
        kwargs["model"] = os.environ["MASON_MODEL"]
    if os.environ.get("MASON_BASE_URL"):
        kwargs["base_url"] = os.environ["MASON_BASE_URL"]
    if os.environ.get("MASON_API_KEY"):
        kwargs["api_key"] = os.environ["MASON_API_KEY"]
    if os.environ.get("MASON_DISABLED_TOOLSETS"):
        kwargs["disabled_toolsets"] = [
            t.strip() for t in os.environ["MASON_DISABLED_TOOLSETS"].split(",") if t.strip()]
    try:
        kwargs["max_iterations"] = int(os.environ.get("MASON_MAX_TURNS", "30"))
    except ValueError:
        kwargs["max_iterations"] = 30
    with contextlib.redirect_stdout(io.StringIO()):
        agent = AIAgent(**kwargs)
    _AGENTS[session_id] = agent
    return agent


def _handle(req: dict) -> dict:
    rid = req.get("id")
    op = str(req.get("op") or "")
    if op == "health":
        return {"id": rid, "ok": True, "cached_sessions": sorted(_AGENTS)}
    if op == "chat":
        sid = str(req.get("session_id") or "tui-1")
        msg = str(req.get("message") or "")
        if not msg.strip():
            return {"id": rid, "ok": False, "error": "empty message"}
        turn = _TURNS.get(sid)
        if turn is not None and turn["thread"].is_alive():
            return {"id": rid, "ok": False, "error": "a turn is already running — /stop first"}
        import threading
        try:
            agent = _agent_for(sid)
        except Exception as e:
            return {"id": rid, "ok": False, "error": f"{type(e).__name__}: {e}"[:500]}

        def _run():
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    result = agent.run_conversation(
                        msg,
                        stream_callback=lambda delta: _emit({"id": rid, "chunk": str(delta or "")}),
                    )
            except Exception as e:
                _emit({"id": rid, "ok": False,
                       "error": f"{type(e).__name__}: {e}"[:500]})
                _TURNS.pop(sid, None)
                return
            if isinstance(result, dict):
                reply = result.get("final_response") or ""
            else:
                reply = str(result or "")
            _emit({"id": rid, "ok": True, "reply": reply})
            _TURNS.pop(sid, None)

        _TURNS[sid] = {"thread": threading.Thread(target=_run, daemon=True, name=f"tui-{sid}")}
        _TURNS[sid]["thread"].start()
        return {"id": rid, "ok": True, "started": True}
    if op == "stop":
        sid = str(req.get("session_id") or "tui-1")
        agent = _AGENTS.get(sid)
        if agent is None:
            return {"id": rid, "ok": False, "error": "no such session"}
        try:
            agent._interrupt_requested = True
            hard = getattr(agent, "_hard_interrupt_requested", None)
            if hard is not None and hasattr(hard, "set"):
                hard.set()  # type: ignore[union-attr]
        except Exception as e:
            return {"id": rid, "ok": False, "error": f"stop failed: {e}"[:200]}
        return {"id": rid, "ok": True, "stopped": True}
    if op == "close":
        sid = str(req.get("session_id") or "tui-1")
        turn = _TURNS.get(sid)
        if turn is not None and turn["thread"].is_alive():
            return {"id": rid, "ok": False, "error": "turn running — /stop first, then /close"}
        try:
            from sessions.manager import on_session_close
            with contextlib.redirect_stdout(io.StringIO()):
                on_session_close(sid)
        except Exception as e:
            return {"id": rid, "ok": False, "error": f"close failed: {e}"[:300]}
        _AGENTS.pop(sid, None)
        return {"id": rid, "ok": True, "closed": True}
    return {"id": rid, "ok": False, "error": f"unknown op: {op}"}


def main() -> None:
    _assert_repo_import()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _emit({"id": None, "ok": False, "error": "bad json"})
            continue
        try:
            resp = _handle(req if isinstance(req, dict) else {})
        except Exception as e:  # never kill the bridge on a bad turn
            resp = {"id": (req.get("id") if isinstance(req, dict) else None),
                    "ok": False, "error": f"bridge: {e}"[:300]}
        _emit(resp)


if __name__ == "__main__":
    main()
