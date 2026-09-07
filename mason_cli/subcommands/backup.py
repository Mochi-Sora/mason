"""``mason backup`` subcommand parser."""

from __future__ import annotations

from typing import Callable


def build_backup_parser(subparsers, *, cmd_backup: Callable) -> None:
    """Attach the ``backup`` subcommand to ``subparsers``."""
    backup_parser = subparsers.add_parser(
        "backup", help="Back up Mason home directory to a zip file",
        description="Create a zip archive of your entire Mason configuration, "
        "skills, sessions, and data (excludes the mason-agent codebase). "
        "Use --quick for a fast snapshot of just critical state files.")
    backup_parser.add_argument(
        "-o",
        "--output", help="Output path for the zip file (default: ~/mason-backup-<timestamp>.zip)")
    backup_parser.add_argument(
        "-q", "--quick", action="store_true",
        help="Quick snapshot: only critical state files (config, state.db, .env, auth, cron)")
    backup_parser.add_argument(
        "-l", "--label", help="Label for the snapshot (only used with --quick)")
    backup_parser.set_defaults(func=cmd_backup)
