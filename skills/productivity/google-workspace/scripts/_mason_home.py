"""Resolve MASON_HOME for standalone skill scripts.

Skill scripts may run outside the Mason process (e.g. system Python,
nix env, CI) where ``mason_constants`` is not importable.  This module
provides the same ``get_mason_home()`` and ``display_mason_home()``
contracts as ``mason_constants`` without requiring it on ``sys.path``.

When ``mason_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``mason_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``MASON_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from mason_constants import display_mason_home as display_mason_home
    from mason_constants import get_mason_home as get_mason_home
except (ModuleNotFoundError, ImportError):

    def get_mason_home() -> Path:
        """Return the Mason home directory (default: ~/.mason).

        Mirrors ``mason_constants.get_mason_home()``."""
        val = os.environ.get("MASON_HOME", "").strip()
        return Path(val) if val else Path.home() / ".mason"

    def display_mason_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``mason_constants.display_mason_home()``."""
        home = get_mason_home()
        try:
            return "~/" + home.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(home)
