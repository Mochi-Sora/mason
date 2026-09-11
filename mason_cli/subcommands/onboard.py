"""``mason onboard`` subcommand parser (self-contained, curator-style)."""

from __future__ import annotations


def cmd_onboard(args) -> int:
    from mason_cli.onboard import run, render
    report = run(check_only=bool(getattr(args, "check_only", False)),
                 fetch=bool(getattr(args, "yes", False)))
    out = render(report)
    # Render Rich markup when available, else plain
    try:
        from rich.console import Console
        Console().print(out)
    except Exception:
        # Strip Rich tags for plain fallback
        import re as _re
        print(_re.sub(r"\[/?[^\]]*\]", "", out))
    return 0 if report["ready"] else 1


def build_onboard_parser(subparsers) -> None:
    """Attach the ``onboard`` subcommand to ``subparsers``."""
    p = subparsers.add_parser(
        "onboard", help="First-run setup check: deps, 1B model, server, smoke test",
        description="Verifies the local-first setup (Python, git, 1B GGUF, "
                    "llama-server, TUI deps), writes a minimal config.yaml if "
                    "missing, and finishes with a real 1B smoke test. "
                    "--check-only reports without writing anything.")
    p.add_argument("--check-only", action="store_true",
                   help="Report only; no writes, no downloads.")
    p.add_argument("--yes", action="store_true",
                   help="Also download the ~400MB 1B model if missing.")
    p.set_defaults(func=cmd_onboard)
