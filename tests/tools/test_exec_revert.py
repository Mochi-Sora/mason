"""Revertable terminal executions: journal, snapshot, restore.

Every layer is real-filesystem, no mocks: git worktrees in tmp repos,
plain dirs for copy snapshots, real trash (never delete).
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

from tools import exec_revert as ev


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "mason-home"
    h.mkdir()
    monkeypatch.setenv("MASON_HOME", str(h))
    # mason_constants caches home — patch the module's view
    import mason_constants
    monkeypatch.setattr(mason_constants, "get_mason_home", lambda: h)
    return h


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "a.txt").write_text("v1")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=path, check=True)
    return path


class TestGitRevert:
    def test_modify_and_new_file_restored(self, home, tmp_path):
        repo = _git_repo(tmp_path / "repo")
        e = ev.snapshot_before("echo hi >> a.txt", str(repo), "s1")
        assert e["reversible"] and e["snapshot"]
        (repo / "a.txt").write_text("vandalized")
        (repo / "new.txt").write_text("oops")
        r = ev.revert(e["id"][:8])
        assert r["ok"], r
        assert (repo / "a.txt").read_text() == "v1"
        assert not (repo / "new.txt").exists()  # parked in the safety stash
        stash = subprocess.run(["git", "-C", str(repo), "stash", "list"],
                               capture_output=True, text=True).stdout
        assert f"mason-revert-{e['id']}-safety" in stash

    def test_revert_last(self, home, tmp_path):
        repo = _git_repo(tmp_path / "repo")
        ev.snapshot_before("true", str(repo), "s1")
        (repo / "a.txt").write_text("v2")
        r = ev.revert("last", session_id="s1")
        assert r["ok"]
        assert (repo / "a.txt").read_text() == "v1"

    def test_journal_only_has_no_snapshot(self, home, tmp_path):
        e = ev.snapshot_before("true", "/nonexistent-dir-xyz", "s1")
        assert not e["snapshot"]
        r = ev.revert(e["id"])
        assert not r["ok"]


class TestCopyRevert:
    def test_plain_dir_roundtrip(self, home, tmp_path):
        d = tmp_path / "work"
        d.mkdir()
        (d / "keep.txt").write_text("orig")
        e = ev.snapshot_before("cmd", str(d), "s1")
        assert e["reversible"]
        (d / "keep.txt").write_text("changed")
        (d / "stray.txt").write_text("x")
        r = ev.revert(e["id"])
        assert r["ok"], r
        assert (d / "keep.txt").read_text() == "orig"
        assert not (d / "stray.txt").exists()

    def test_oversize_dir_journal_only(self, home, tmp_path, monkeypatch):
        import tools.exec_revert as E
        monkeypatch.setattr(E, "DEFAULTS", {"enabled": True, "max_snapshot_mb": 0, "retain": 5})
        d = tmp_path / "big"
        d.mkdir()
        (d / "f.txt").write_text("x" * 100)
        e = ev.snapshot_before("cmd", str(d), "s1")
        assert not e["snapshot"] and "cap" in e["note"]


class TestJournal:
    def test_list_and_ids(self, home, tmp_path):
        d = tmp_path / "w"
        d.mkdir()
        e1 = ev.snapshot_before("echo one", str(d), "s9")
        e2 = ev.snapshot_before("echo two", str(d), "s9")
        ids = [e["id"] for e in ev.read_log("s9")]
        assert e2["id"] in ids and e1["id"] in ids
        assert ev.read_log("other") == []

    def test_prune_retain(self, home, tmp_path):
        d = tmp_path / "w"
        d.mkdir()
        (d / "f").write_text("x")
        for i in range(4):
            ev.snapshot_before(f"cmd{i}", str(d), "s-prune")
        import tools.exec_revert as E
        E._prune("s-prune", 2)
        left = list((home / "snapshots" / "s-prune").iterdir())
        assert len(left) == 2
