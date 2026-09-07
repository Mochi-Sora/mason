"""Resolve MASON_HOME for standalone skill scripts.

Skill scripts may run outside the Mason process (system Python, nix env,
CI) where ``mason_constants`` is not importable.  This module provides the
same ``get_mason_home()`` contract without requiring it on ``sys.path``.

When ``mason_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from mason_constants import get_mason_home as get_mason_home
except (ModuleNotFoundError, ImportError):

    def get_mason_home() -> Path:
        """Return the Mason home directory (default: ``~/.mason``)."""
        val = os.environ.get("MASON_HOME", "").strip()
        return Path(val) if val else Path.home() / ".mason"
