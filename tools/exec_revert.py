"""Revertable terminal executions (local backend).

Every agent terminal command is journaled to <MASON_HOME>/exec_log.jsonl with a
pre-execution snapshot:
  - git worktree  -> {head sha, status} — revert = safety-stash, reset --hard,
                     untracked moved to trash, then clean. Exact, near-free.
  - other dirs    -> bounded full copy (skip junk, size cap) — revert = copy
                     back, strays moved to trash.
  - remote backends (ssh/docker/...) -> journal only, honestly marked.

External side effects (network, sent messages, non-file state) can NEVER be
undone anywhere — the journal marks them irreversible so nobody pretends.

`mason revert` / the exec_revert model tool restore by journal id (or "last").
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCK = threading.Lock()

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
             "target", "dist", "build", ".mypy_cache", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".pyo", ".gguf", ".onnx", ".tflite", ".bin"}

DEFAULTS = {"enabled": True, "max_snapshot_mb": 100, "retain": 20}


def _cfg() -> dict:
    cfg = dict(DEFAULTS)
    try:
        from mason_cli.config import load_config
        raw = (load_config() or {}).get("tools", {}).get("terminal", {}).get("revert", {})
        if isinstance(raw, dict):
            for k in cfg:
                if raw.get(k) is not None:
                    cfg[k] = raw[k]
    except Exception:
        pass
    try:
        if os.environ.get("MASON_REVERT", "") == "off":
            cfg["enabled"] = False
    except Exception:
        pass
    return cfg


def _home() -> Path:
    try:
        from mason_constants import get_mason_home
        return Path(get_mason_home())
    except Exception:
        return Path.home() / ".mason"


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


def _snap_id(session_id: str, command: str, cwd: str) -> str:
    raw = f"{session_id}|{_now()}|{cwd}|{command}".encode()
    return hashlib.sha1(raw).hexdigest()[:12]


def _git_head(cwd: Path) -> Optional[str]:
    try:
        r = subprocess.run(["git", "-C", str(cwd), "rev-parse", "HEAD"],
                           capture_output=True, timeout=15, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def _dir_size(root: Path) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if any(f.endswith(s) for s in SKIP_SUFFIX):
                continue
            try:
                total += (Path(dirpath) / f).stat().st_size
            except OSError:
                continue
    return total


def _copy_tree(src: Path, dst: Path) -> None:
    def _ignore(d, names):
        return [n for n in names
                if n in SKIP_DIRS or any(n.endswith(s) for s in SKIP_SUFFIX)]
    shutil.copytree(src, dst, ignore=_ignore, symlinks=True)


def snapshot_before(command: str, cwd: str, session_id: str, background: bool = False,
                    backend: str = "local") -> dict:
    """Journal + snapshot. Returns the journal entry (with id). Never raises."""
    entry: dict = {"id": "", "ts": _now(), "sid": session_id or "default",
                   "cmd": command[:500], "cwd": cwd, "backend": backend,
                   "background": bool(background), "snapshot": None,
                   "reversible": False, "note": ""}
    try:
        cfg = _cfg()
        entry["id"] = _snap_id(entry["sid"], command, cwd)
        if not cfg.get("enabled", True):
            entry["note"] = "revert disabled by config"
            _append(entry)
            return entry
        if backend != "local":
            entry["note"] = f"remote backend ({backend}): journal only, no snapshot"
            _append(entry)
            return entry
        root = Path(cwd or ".").expanduser().resolve()
        if not root.is_dir():
            entry["note"] = "cwd not a dir — journal only"
            _append(entry)
            return entry
        head = _git_head(root)
        snapdir = _home() / "snapshots" / entry["sid"] / entry["id"]
        if head:
            snapdir.mkdir(parents=True, exist_ok=True)
            (snapdir / "meta.json").write_text(json.dumps(
                {"kind": "git", "head": head, "cwd": str(root)}))
            entry.update(snapshot=str(snapdir), reversible=True,
                         note=f"git worktree @ {head[:8]}")
        else:
            size_mb = _dir_size(root) / (1024 * 1024)
            cap = float(cfg.get("max_snapshot_mb", 100))
            if size_mb > cap:
                entry["note"] = f"dir {size_mb:.0f}MB > cap {cap:.0f}MB — journal only"
            else:
                snapdir.mkdir(parents=True, exist_ok=True)
                _copy_tree(root, snapdir / "tree")
                (snapdir / "meta.json").write_text(json.dumps(
                    {"kind": "copy", "cwd": str(root)}))
                entry.update(snapshot=str(snapdir), reversible=True,
                             note=f"full copy {size_mb:.1f}MB")
        _append(entry)
        _prune(entry["sid"], int(cfg.get("retain", 20)))
    except Exception as e:
        entry["note"] = f"snapshot failed ({e}); journal only"
        try:
            _append(entry)
        except Exception:
            pass
    return entry


def _append(entry: dict) -> None:
    with _LOCK:
        with open(_home() / "exec_log.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")


def read_log(session_id: str = "", limit: int = 20) -> List[dict]:
    try:
        lines = (_home() / "exec_log.jsonl").read_text().splitlines()
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if session_id and e.get("sid") != session_id:
            continue
        out.append(e)
        if len(out) >= limit:
            break
    return out


def _trash(snapdir: Path) -> Path:
    t = snapdir / "trash"
    t.mkdir(parents=True, exist_ok=True)
    return t


def _revert_git(entry: dict, snapdir: Path) -> tuple[bool, str]:
    meta = json.loads((snapdir / "meta.json").read_text())
    cwd, head = meta["cwd"], meta["head"]
    cur = _git_head(Path(cwd))
    if cur is None:
        return False, "not a git worktree anymore"
    if cur != head:
        # Someone committed after the snapshot — resetting would destroy THEIR
        # history. Refuse loudly instead of guessing.
        return False, (f"worktree moved on ({cur[:8]} != snapshot {head[:8]}): "
                       "commit/stash your work or reset manually; refusing to destroy history")
    # Safety net first: everything (tracked + untracked) into a labeled stash,
    # so the pre-revert state — including stray new files — is recoverable via
    # git stash show/apply, never deleted.
    r = subprocess.run(["git", "-C", cwd, "stash", "push", "-u", "-m",
                        f"mason-revert-{entry['id']}-safety"],
                       capture_output=True, timeout=60, text=True)
    if r.returncode != 0 and "No local changes" not in (r.stdout + r.stderr):
        return False, f"safety stash failed: {(r.stdout + r.stderr).strip()[:200]}"
    r = subprocess.run(["git", "-C", cwd, "reset", "--hard", head],
                       capture_output=True, timeout=120, text=True)
    if r.returncode != 0:
        return False, f"reset failed: {r.stderr.strip()[:200]}"
    return True, (f"restored {head[:8]}; pre-revert state (incl. new files) stashed as "
                  f"mason-revert-{entry['id']}-safety — `git stash show` / `apply` to recover pieces")


def _revert_copy(entry: dict, snapdir: Path) -> tuple[bool, str]:
    meta = json.loads((snapdir / "meta.json").read_text())
    cwd, tree = Path(meta["cwd"]), snapdir / "tree"
    if not tree.is_dir():
        return False, "snapshot tree missing"
    if not cwd.is_dir():
        return False, "cwd gone — nothing to restore into"
    trash = _trash(snapdir)
    # files present now but absent in snapshot -> trash
    want = {p.relative_to(tree) for p in tree.rglob("*") if p.is_file() or p.is_symlink()}
    for p in sorted((cwd).rglob("*")):
        if not (p.is_file() or p.is_symlink()):
            continue
        try:
            rel = p.relative_to(cwd)
        except ValueError:
            continue
        if rel not in want:
            try:
                dest = trash / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dest))
            except OSError:
                continue
    # snapshot files back
    for src in tree.rglob("*"):
        if not (src.is_file() or src.is_symlink()):
            continue
        rel = src.relative_to(tree)
        dest = cwd / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_symlink() or dest.exists():
                if dest.is_dir() and not dest.is_symlink():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            if src.is_symlink():
                dest.symlink_to(os.readlink(src))
            else:
                shutil.copy2(src, dest)
        except OSError:
            continue
    return True, f"restored {len(want)} files from snapshot (strays in snapshot trash)"


def revert(target: str, session_id: str = "") -> dict:
    """Restore journal entry `target` (id prefix or 'last'). Never raises."""
    try:
        entries = read_log(session_id, limit=200)
        entry = None
        if target == "last":
            entry = next((e for e in entries if e.get("snapshot")), None)
            if entry is None:
                return {"ok": False, "error": "no snapshots in journal"}
        else:
            entry = next((e for e in entries if str(e.get("id", "")).startswith(target)), None)
            if entry is None:
                return {"ok": False, "error": f"no journal entry matching '{target}'"}
        if not entry.get("snapshot"):
            return {"ok": False, "error": f"entry {entry['id']} has no snapshot ({entry.get('note', 'journal only')})"}
        snapdir = Path(entry["snapshot"])
        try:
            meta = json.loads((snapdir / "meta.json").read_text())
        except Exception:
            return {"ok": False, "error": "snapshot data missing (pruned?)"}
        kind = meta.get("kind")
        if kind == "git":
            ok, msg = _revert_git(entry, snapdir)
        elif kind == "copy":
            ok, msg = _revert_copy(entry, snapdir)
        else:
            return {"ok": False, "error": f"unknown snapshot kind {kind!r}"}
        return {"ok": ok, "id": entry["id"],
                "restored": msg if ok else "", "error": "" if ok else msg,
                "warning": ("external effects (network/sent data) are NOT undone — "
                            "filesystem only")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _prune(session_id: str, retain: int) -> None:
    try:
        root = _home() / "snapshots" / session_id
        if not root.is_dir():
            return
        dirs = sorted([d for d in root.iterdir() if d.is_dir()],
                      key=lambda d: d.stat().st_mtime)
        for d in dirs[:-max(1, retain)]:
            shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


EXEC_REVERT_SCHEMA = {
    "name": "exec_revert",
    "description": ("Undo an agent terminal execution: list the journal or restore "
                    "the filesystem to before a command (git worktree: reset to pinned "
                    "HEAD with safety stash; other dirs: snapshot copy back). "
                    "External effects are never undone."),
    "parameters": {"type": "object",
                   "properties": {
                       "action": {"type": "string",
                                  "description": "'list' (recent journal) or 'revert'.",
                                  "enum": ["list", "revert"]},
                       "target": {"type": "string",
                                  "description": "Journal id prefix or 'last' (for revert)."}},
                   "required": ["action"]},
}


def _exec_revert_handler(args: dict, **kw) -> str:
    import json as _json
    action = str((args or {}).get("action", "list")).strip().lower()
    if action == "revert":
        return _json.dumps(revert(str((args or {}).get("target", "last")),
                                  str(kw.get("current_session_id") or "")))
    entries = read_log(str(kw.get("current_session_id") or ""), limit=15)
    return _json.dumps([{"id": e.get("id"), "ts": e.get("ts"), "cmd": (e.get("cmd") or "")[:120],
                         "snapshot": bool(e.get("snapshot")), "note": e.get("note", "")}
                        for e in entries])


try:
    from tools.registry import registry as _registry
    _registry.register(name="exec_revert", toolset="terminal", schema=EXEC_REVERT_SCHEMA,
                       handler=_exec_revert_handler)
except Exception:
    pass
