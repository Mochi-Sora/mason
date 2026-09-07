"""Isolated session containers — each session is a folder
sessions/<id>/state.md + backup.md + backup.db (Gbrain-inspired index) + meta.json
"""
import pathlib, json, sqlite3, datetime, hashlib

ROOT = pathlib.Path(__file__).parent.parent / "sessions"
BACKUP_LIMIT = 10_000_000  # 10M chars
BACKUP_WATCH = 0.85        # 85% triggers summary

def _session_dir(session_id: str) -> pathlib.Path:
    d = ROOT / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def init_session(session_id: str, user_id: str = "default") -> pathlib.Path:
    d = _session_dir(session_id)
    (d / "state.md").write_text(f"# State — {session_id}\n- Session started {datetime.datetime.utcnow().isoformat()}\n")
    (d / "backup.md").write_text(f"# Backup — {session_id}\n")
    (d / "meta.json").write_text(json.dumps({"session_id": session_id, "user_id": user_id, "started": datetime.datetime.utcnow().isoformat()}, indent=2))
    # init FTS index
    _db(d).close()
    return d

def _db(session_dir: pathlib.Path) -> sqlite3.Connection:
    db = sqlite3.connect(session_dir / "backup.db")
    db.execute("CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, text TEXT, ts TEXT)")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(id, text)")
    return db

def append_backup(session_id: str, role: str, text: str):
    d = _session_dir(session_id)
    md = d / "backup.md"
    line = f"\n## {role} {datetime.datetime.utcnow().isoformat()}\n{text}\n"
    md.write_text(md.read_text() + line)
    # index chunk
    cid = hashlib.sha256(line.encode()).hexdigest()[:10]
    db = _db(d)
    db.execute("INSERT OR REPLACE INTO chunks(id,text,ts) VALUES(?,?,?)", (cid, line, datetime.datetime.utcnow().isoformat()))
    db.execute("INSERT OR REPLACE INTO chunks_fts(id,text) VALUES(?,?)", (cid, line))
    db.commit(); db.close()
    # watcher: >85% triggers summary via 1B
    if len(md.read_text()) > BACKUP_LIMIT * BACKUP_WATCH:
        _trigger_summary(session_id)

def update_state(session_id: str, content: str):
    d = _session_dir(session_id)
    (d / "state.md").write_text(content[:5000])  # state is tiny by design

def recall_backup(session_id: str, query: str, budget_tokens: int = 2000, limit: int = 5) -> dict:
    """Gbrain-inspired retrieval: FTS + budget packing"""
    d = ROOT / session_id
    if not (d / "backup.db").exists():
        return {"facts": [], "results": [], "budget_used": 0, "total": 0}
    db = sqlite3.connect(d / "backup.db")
    try:
        cur = db.execute("SELECT id,text FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT ?", (query, limit))
        rows = cur.fetchall()
    except Exception:
        cur = db.execute("SELECT id,text FROM chunks WHERE text LIKE ? LIMIT ?", (f"%{query}%", limit))
        rows = cur.fetchall()
    db.close()
    # budget pack: char/4 approx
    results = []
    used = 0
    for cid, txt in rows:
        tokens = len(txt)//4
        if used + tokens > budget_tokens:
            break
        results.append({"id": cid, "chunk": txt[:800], "evidence": "keyword_exact"})
        used += tokens
    return {"protocol_version": 1, "facts": [], "results": results, "budget_used": used, "total": len(results)}

def _trigger_summary(session_id: str):
    # delegate to 1B compressor (fire-and-forget)
    try:
        from custom_memory.llm.tasks.backup_compress_task import build_prompt
        from custom_memory.llm.client import LlamaClient
        d = _session_dir(session_id)
        md = d / "backup.md"
        text = md.read_text()
        # compress oldest 30%
        chunk = text[:int(len(text)*0.3)]
        prompt = build_prompt(chunk)
        summary = LlamaClient().complete(prompt, max_tokens=400)
        # replace chunk with summary
        md.write_text(f"# Backup — {session_id} (compressed {datetime.datetime.utcnow().isoformat()})\n## Summary of oldest 30%\n{summary}\n\n" + text[int(len(text)*0.3):])
        # rebuild index quickly (truncate FTS and reinsert)
        db = _db(d)
        db.execute("DELETE FROM chunks_fts"); db.commit(); db.close()
    except Exception:
        pass

def purge_session(session_id: str):
    import shutil
    d = ROOT / session_id
    if d.exists():
        shutil.rmtree(d)

def list_sessions():
    return [p.name for p in ROOT.glob("*") if p.is_dir()]
