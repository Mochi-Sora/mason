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
