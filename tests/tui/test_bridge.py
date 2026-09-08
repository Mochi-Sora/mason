"""TUI bridge protocol tests (no model needed).

Covers the JSON-RPC envelope: health, unknown ops, bad input, close flow.
Live chat turns need a model and are verified manually (see README ops).
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BRIDGE = REPO / "tui" / "bridge.py"


@pytest.fixture(scope="module")
def bridge():
    sys.path.insert(0, str(REPO / "tui"))
    sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("tui_bridge", BRIDGE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod


class TestEnvelope:
    def test_health(self, bridge):
        r = bridge._handle({"id": 1, "op": "health"})
        assert r == {"id": 1, "ok": True, "cached_sessions": []}

    def test_unknown_op(self, bridge):
        r = bridge._handle({"id": 2, "op": "frobnicate"})
        assert r["id"] == 2 and r["ok"] is False and "frobnicate" in r["error"]

    def test_empty_chat_rejected(self, bridge):
        r = bridge._handle({"id": 3, "op": "chat", "session_id": "x", "message": "   "})
        assert r["ok"] is False

    def test_close_missing_session_ok(self, bridge, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = bridge._handle({"id": 4, "op": "close", "session_id": "nope"})
        assert r == {"id": 4, "ok": True, "closed": True}

    def test_repo_guard(self, bridge):
        # Must resolve run_agent from this tree, never site-packages.
        import run_agent
        assert Path(run_agent.__file__).resolve() == (REPO / "run_agent.py").resolve()


class StubAgent:
    def __init__(self):
        self._interrupt_requested = False
        self.calls = []

    def run_conversation(self, msg, stream_callback=None):
        self.calls.append(msg)
        if stream_callback:
            stream_callback("streaming ")
            stream_callback("works")
        return {"final_response": "stub reply"}


class TestStreamingTurn:
    def test_chat_streams_then_replies(self, bridge):
        import time
        agent = StubAgent()
        bridge._AGENTS["s-stream"] = agent
        got = {}

        # drive _handle on a thread like main() would; collect emissions
        seen = []
        orig_emit = bridge._emit
        bridge._emit = seen.append
        try:
            ack = bridge._handle({"id": 10, "op": "chat", "session_id": "s-stream", "message": "hi"})
            assert ack == {"id": 10, "ok": True, "started": True}
            deadline = time.time() + 10
            while "s-stream" in bridge._TURNS and time.time() < deadline:
                time.sleep(0.05)
            assert "s-stream" not in bridge._TURNS
        finally:
            bridge._emit = orig_emit
            bridge._AGENTS.pop("s-stream", None)
        kinds = [( "chunk" in m, m.get("ok")) for m in seen]
        assert any(k[0] for k in kinds), "no chunk emitted"
        finals = [m for m in seen if "ok" in m]
        assert finals and finals[-1] == {"id": 10, "ok": True, "reply": "stub reply"}
        assert agent.calls == ["hi"]

    def test_stop_sets_interrupt(self, bridge):
        agent = StubAgent()
        bridge._AGENTS["s-stop"] = agent
        try:
            r = bridge._handle({"id": 11, "op": "stop", "session_id": "s-stop"})
            assert r == {"id": 11, "ok": True, "stopped": True}
            assert agent._interrupt_requested is True
        finally:
            bridge._AGENTS.pop("s-stop", None)

    def test_busy_second_chat_refused(self, bridge):
        import threading
        import time

        class Slow(StubAgent):
            def run_conversation(self, msg, stream_callback=None):
                time.sleep(2)
                return {"final_response": "late"}

        bridge._AGENTS["s-busy"] = Slow()
        try:
            ack = bridge._handle({"id": 12, "op": "chat", "session_id": "s-busy", "message": "one"})
            assert ack["ok"] is True
            busy = bridge._handle({"id": 13, "op": "chat", "session_id": "s-busy", "message": "two"})
            assert busy["ok"] is False and "/stop" in busy["error"]
            close = bridge._handle({"id": 14, "op": "close", "session_id": "s-busy"})
            assert close["ok"] is False and "/stop" in close["error"]
        finally:
            t = bridge._TURNS.pop("s-busy", None)
            if t:
                t["thread"].join(timeout=5)
            bridge._AGENTS.pop("s-busy", None)
