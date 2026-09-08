"""Onboarding: checks report honestly, config never overwritten, no surprises.

- check-only performs zero writes (no config, no download).
- ensure_config creates a minimal file once, then leaves it alone.
- run() readiness ignores graceful degradations (model/server/TUI/smoke).
- render() surfaces a fix line for every failure.
"""
import sys
from pathlib import Path

from mason_cli import onboard as ob


class TestPureChecks:
    def test_python_check_shape(self):
        s = ob.check_python()
        assert set(s) == {"name", "ok", "msg", "fix"}
        assert s["ok"] is True  # test env runs 3.11+

    def test_missing_bin_reports_fix(self, monkeypatch):
        monkeypatch.setattr(ob.shutil, "which", lambda name: None)
        s = ob.check_bin("llama-server", why="serves 1B", brew="llama.cpp", required=False)
        assert s["ok"] is True  # optional passes
        assert s["fix"]  # but still tells you how to get it

    def test_required_missing_bin_fails(self, monkeypatch):
        monkeypatch.setattr(ob.shutil, "which", lambda name: None)
        s = ob.check_bin("git", why="snapshots")
        assert s["ok"] is False and s["fix"]

    def test_model_missing_points_at_onboard_yes(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ob, "model_dest", lambda: tmp_path / "nope.gguf")
        s = ob.check_model()
        assert s["ok"] is False and "--yes" in s["fix"]

    def test_model_present_passes(self, monkeypatch, tmp_path):
        f = tmp_path / "m.gguf"
        f.write_bytes(b"x" * (ob.MODEL_MIN_BYTES + 1))
        monkeypatch.setattr(ob, "model_dest", lambda: f)
        assert ob.check_model()["ok"] is True

    def test_server_down_reports_start_cmd(self, monkeypatch):
        monkeypatch.setattr(ob.urllib.request, "urlopen", _boom)
        s = ob.check_server()
        assert s["ok"] is False and "llama-server" in s["fix"]


def _boom(*a, **k):
    raise ConnectionError("down")


class TestConfigSafety:
    def test_check_only_writes_nothing(self, monkeypatch, tmp_path):
        home = tmp_path / "h"
        monkeypatch.setattr(ob, "mason_home", lambda: home)
        ob.collect(write_config=False)
        assert not (home / "config.yaml").exists()

    def test_ensure_config_never_overwrites(self, monkeypatch, tmp_path):
        home = tmp_path / "h"
        home.mkdir()
        monkeypatch.setattr(ob, "mason_home", lambda: home)
        first = ob.ensure_config()
        assert first["ok"] and (home / "config.yaml").exists()
        (home / "config.yaml").write_text("mine: true\n")
        second = ob.ensure_config()
        assert second["ok"] and (home / "config.yaml").read_text() == "mine: true\n"


class TestRunContract:
    def test_ready_ignores_graceful_gaps(self, monkeypatch, tmp_path):
        home = tmp_path / "h"
        monkeypatch.setattr(ob, "mason_home", lambda: home)
        monkeypatch.setattr(ob.shutil, "which",
                            lambda n: "/usr/bin/" + n if n in {"git", "python3"} else None)
        monkeypatch.setattr(ob, "model_dest", lambda: tmp_path / "nope.gguf")
        monkeypatch.setattr(ob.urllib.request, "urlopen", _boom)
        report = ob.run(check_only=True, run_smoke=False)
        names = {s["name"] for s in report["steps"]}
        assert {"1B model", "llama-server :8080", "TUI deps"} <= names
        assert report["ready"] is True  # CLI still chats; gaps are warnings

    def test_missing_git_blocks_ready(self, monkeypatch, tmp_path):
        home = tmp_path / "h"
        monkeypatch.setattr(ob, "mason_home", lambda: home)
        monkeypatch.setattr(ob.shutil, "which", lambda n: None)
        report = ob.run(check_only=True, run_smoke=False)
        assert report["ready"] is False

    def test_render_shows_fixes(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ob.shutil, "which", lambda n: None)
        report = ob.run(check_only=True, run_smoke=False)
        text = ob.render(report)
        assert "→" in text and "NOT READY" in text
