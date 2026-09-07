"""`mason update` must self-heal the ``mason-acp`` launcher.

ACP hosts (Zed, JetBrains, Buzz Desktop) resolve the agent by the
``mason-acp`` command name on the login-shell PATH. Fresh installs get the
launcher from ``scripts/install.sh``; existing installs get it from
``_ensure_acp_launcher()`` during ``mason update``.
"""

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from mason_cli.update_cmd import _ensure_acp_launcher


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("MASON_HOME", str(tmp_path / ".mason"))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    return bin_dir








def test_does_not_follow_symlink_into_venv(fake_home, tmp_path):
    """#21454 failure mode: never write through a symlinked mason-acp."""
    (fake_home / "mason").write_text("#!/bin/sh\n", encoding="utf-8")
    console_script = tmp_path / "venv" / "bin" / "mason-acp"
    console_script.parent.mkdir(parents=True)
    marker = "#!/usr/bin/env python\n# real console script\n"
    console_script.write_text(marker, encoding="utf-8")
    (fake_home / "mason-acp").symlink_to(console_script)

    _ensure_acp_launcher()

    assert console_script.read_text(encoding="utf-8") == marker
    assert (fake_home / "mason-acp").is_symlink()






def test_unwritable_bin_dir_is_skipped(fake_home):
    (fake_home / "mason").write_text("#!/bin/sh\n", encoding="utf-8")
    if not hasattr(os, "geteuid"):
        # Windows: no geteuid, and chmod can't make a directory unwritable
        # anyway. _ensure_acp_launcher is an explicit no-op there, so the
        # assertion below still holds — vacuously.
        _ensure_acp_launcher()
        assert not (fake_home / "mason-acp").exists()
        return
    if os.geteuid() == 0:
        pytest.skip("root ignores directory write permissions")
    fake_home.chmod(0o555)
    try:
        _ensure_acp_launcher()  # must not raise
        assert not (fake_home / "mason-acp").exists()
    finally:
        fake_home.chmod(0o755)
