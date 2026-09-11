"""Mason first-run onboarding: deps, 1B model, server, smoke test.

``mason onboard``     full pass (checks + writes minimal config; downloads the
                      ~400MB GGUF only with --yes after showing the plan).
``mason onboard --check-only``   report only, no writes, no downloads.
``mason onboard --yes``          also fetch a missing model automatically.

Defaults are already local-first, so onboarding CREATES almost nothing: a
minimal config.yaml (only if missing), the model file, and TUI node_modules
(via npm, only with --yes). Everything else is verified, not installed —
package installs stay the operator's explicit choice (brew/apt/pacman hints
are printed per-OS).
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

MODEL_FILE = "qwen2-0_5b-instruct-q4_k_m.gguf"
MODEL_URL = ("https://huggingface.co/Qwen/Qwen2-0.5B-Instruct-GGUF/resolve/main/"
             + MODEL_FILE)
MODEL_MIN_BYTES = 300 * 1024 * 1024  # sanity: real file is ~400MB
SERVER_URL = "http://127.0.0.1:8080"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def model_dest() -> Path:
    return repo_root() / "tiered_memory" / "llm" / "models" / MODEL_FILE


def mason_home() -> Path:
    try:
        from mason_constants import get_mason_home
        return Path(get_mason_home())
    except Exception:
        return Path.home() / ".mason"


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def _pkg_hint(*, brew: str = "", apt: str = "", pacman: str = "") -> str:
    sysname = platform.system().lower()
    if sysname == "darwin" and brew:
        return f"brew install {brew}"
    if sysname == "linux":
        if _which("pacman") and pacman:
            return f"sudo pacman -S {pacman}"
        if _which("apt-get") and apt:
            return f"sudo apt-get install {apt}"
    return "install via your package manager"


def check_python() -> Dict[str, Any]:
    ok = sys.version_info >= (3, 11)
    return {"name": "python >= 3.11", "ok": ok,
            "msg": platform.python_version() + (" ✓" if ok else " — need 3.11+"),
            "fix": "" if ok else "install Python 3.11+ (python.org / brew / apt)"}


def check_bin(name: str, *, why: str, brew: str = "", apt: str = "",
              pacman: str = "", required: bool = True) -> Dict[str, Any]:
    path = _which(name)
    ok = path is not None
    return {"name": name, "ok": ok or not required,
            "msg": (path or "missing") + ("" if required else " (optional)") + f" — {why}",
            "fix": "" if ok else _pkg_hint(brew=brew, apt=apt, pacman=pacman)}


def check_mason_pkg() -> Dict[str, Any]:
    try:
        import mason_cli  # noqa: F401
        return {"name": "mason package", "ok": True,
                "msg": "importable (dev install or venv active)", "fix": ""}
    except Exception:
        return {"name": "mason package", "ok": False,
                "msg": "not importable — run from the repo or install it",
                "fix": "cd <mason repo> && pip install -e ."}


def check_model() -> Dict[str, Any]:
    p = model_dest()
    if p.exists() and p.stat().st_size >= MODEL_MIN_BYTES:
        mb = p.stat().st_size / (1024 * 1024)
        return {"name": "1B model", "ok": True, "msg": f"{p} ({mb:.0f}MB)", "fix": ""}
    have = f"found {p} but only {p.stat().st_size / 1024:.0f}KB — partial download" \
        if p.exists() else "missing"
    return {"name": "1B model", "ok": False,
            "msg": f"{have} — memory/evolution run in fallback mode without it",
            "fix": f"mason onboard --yes  (downloads ~400MB from HuggingFace)\n"
                   f"  or manually: curl -L -o {p} {MODEL_URL}"}


def check_server() -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(SERVER_URL + "/health", timeout=5) as r:
            if r.status == 200:
                return {"name": "llama-server :8080", "ok": True,
                        "msg": "live — 1B served over HTTP", "fix": ""}
    except Exception:
        pass
    mp = model_dest()
    start = (f"llama-server -m {mp} --port 8080 "
             f"{'--ctx-size 2048' if True else ''}".strip())
    return {"name": "llama-server :8080", "ok": False,
            "msg": "not reachable — memory/evolution fall back to embedded python (slower first load) or no-op",
            "fix": _pkg_hint(brew="llama.cpp", apt="llama.cpp", pacman="llama.cpp")
                   + f"  then: {start}  (run in background / tmux)"}


def check_tui() -> Dict[str, Any]:
    nm = repo_root() / "tui" / "node_modules"
    if nm.is_dir():
        return {"name": "TUI deps", "ok": True, "msg": "tui/node_modules present", "fix": ""}
    return {"name": "TUI deps", "ok": False,
            "msg": "missing — only matters for the Ink TUI",
            "fix": "cd tui && npm install"}


def ensure_config() -> Dict[str, Any]:
    """Create a minimal config.yaml if none exists. Never overwrites."""
    cfg = mason_home() / "config.yaml"
    if cfg.exists():
        return {"name": "config.yaml", "ok": True, "msg": str(cfg), "fix": ""}
    try:
        mason_home().mkdir(parents=True, exist_ok=True)
        cfg.write_text(
            "# Mason — created by `mason onboard`. Defaults are local-first;\n"
            "# uncomment to change. Full reference: mason_cli/config_defaults.py\n"
            "# tools:\n"
            "#   terminal:\n"
            "#     backend: local   # local | docker | ssh | ...\n"
            "# auxiliary:\n"
            "#   model: qwen2-0_5b-instruct   # local 1B via llama-server :8080\n")
        return {"name": "config.yaml", "ok": True,
                "msg": f"created minimal {cfg}", "fix": ""}
    except Exception as e:
        return {"name": "config.yaml", "ok": False,
                "msg": f"could not write {cfg}: {e}", "fix": f"check permissions on {mason_home()}"}


def fetch_model() -> Dict[str, Any]:
    dest = model_dest()
    if dest.exists() and dest.stat().st_size >= MODEL_MIN_BYTES:
        return {"name": "fetch model", "ok": True, "msg": "already present", "fix": ""}
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".gguf.part")
        urllib.request.urlretrieve(MODEL_URL, tmp)
        if tmp.stat().st_size < MODEL_MIN_BYTES:
            tmp.unlink(missing_ok=True)
            return {"name": "fetch model", "ok": False,
                    "msg": "download too small — aborted (network issue?)",
                    "fix": "retry later: mason onboard --yes"}
        tmp.rename(dest)
        return {"name": "fetch model", "ok": True,
                "msg": f"downloaded {dest} ({dest.stat().st_size / 1024 / 1024:.0f}MB)",
                "fix": ""}
    except Exception as e:
        return {"name": "fetch model", "ok": False,
                "msg": f"download failed: {str(e)[:160]}", "fix": "retry later: mason onboard --yes"}


def smoke() -> Dict[str, Any]:
    """One real 1B completion. Slow on CPU is fine — proves the path works."""
    try:
        sys.path.insert(0, str(repo_root()))
        from tiered_memory.llm.client import LlamaClient
        c = LlamaClient()
        try:
            healthy = bool(c.health().get("server"))
        except Exception:
            healthy = False
        out = c.complete("Reply with exactly: onboard-ok", max_tokens=16, timeout=180)
        if "onboard-ok" in out:
            return {"name": "1B smoke", "ok": True,
                    "msg": f"model replied correctly ({'server' if healthy else 'embedded'})",
                    "fix": ""}
        if "llm unavailable" in out:
            return {"name": "1B smoke", "ok": False,
                    "msg": "no model reachable (server down AND no usable GGUF) — fallback mode",
                    "fix": "fetch the model + start llama-server (see above)"}
        return {"name": "1B smoke", "ok": True,
                "msg": f"model replied (unexpected text, path works): {out[:80]}", "fix": ""}
    except Exception as e:
        return {"name": "1B smoke", "ok": False, "msg": f"smoke error: {e}", "fix": ""}


def collect(*, write_config: bool = True) -> List[Dict[str, Any]]:
    steps = [
        check_python(),
        check_mason_pkg(),
        check_bin("git", why="revert snapshots + version control",
                  brew="git", apt="git", pacman="git"),
        check_bin("rg", why="fast file search (session tools use it)",
                  brew="ripgrep", apt="ripgrep", pacman="ripgrep", required=False),
        check_bin("node", why="Ink TUI runtime",
                  brew="node", apt="nodejs npm", pacman="nodejs npm", required=False),
        check_bin("llama-server", why="serves the 1B model over :8080",
                  brew="llama.cpp", pacman="llama.cpp", required=False),
        check_model(),
        check_server(),
        check_tui(),
    ]
    if write_config:
        steps.append(ensure_config())
    return steps


def run(*, check_only: bool = False, fetch: bool = False,
        run_smoke: bool = True) -> Dict[str, Any]:
    steps = collect(write_config=not check_only)
    if fetch and not check_only:
        steps.append(fetch_model())
        # re-check model + server now that we fetched
        steps.append(check_model())
    if run_smoke:
        steps.append(smoke())
    # READY = can chat in the CLI. Model/server/smoke/TUI degrade gracefully
    # (fallback memory, embedded inference, npm install later) so they warn
    # instead of blocking.
    ready = all(s["ok"] for s in steps
                if s["name"] not in {"1B smoke", "llama-server :8080", "1B model", "TUI deps"})
    return {"steps": steps, "ready": ready, "fetch": fetch, "check_only": check_only}


def render(report: Dict[str, Any]) -> str:
    lines = ["Mason onboard — " + ("check" if report.get("check_only") else "setup")]
    for s in report["steps"]:
        mark = "✓" if s["ok"] else "✗"
        lines.append(f"  [{mark}] {s['name']}: {s['msg']}")
        if not s["ok"] and s.get("fix"):
            for fl in s["fix"].splitlines():
                lines.append(f"       → {fl}")
    lines.append("READY ✓ — run `mason` to chat."
                 if report["ready"] else "NOT READY — fix the ✗ rows above, then re-run `mason onboard`.")
    return "\n".join(lines)
