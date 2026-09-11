"""Long-term: Gbrain-inspired durable store (no dream cycle)
- Pages: long_term_memories/<slug>.md
- Facts: facts.jsonl (entity-linked, provenance)
- FTS: SQLite FTS5 for keyword search
"""
import pathlib, json, sqlite3, datetime, re, hashlib

DIR_NAME = "long_term_memories"
FACTS_FILE = "facts.jsonl"
EDGES_FILE = "edges.jsonl"
DB_FILE = "long_term.db"
_LEGACY_DIR_NAME = DIR_NAME

def _base(base: pathlib.Path | None = None) -> pathlib.Path:
    try:
        from mason_constants import get_mason_home
        d = get_mason_home() / DIR_NAME
    except Exception:
        d = (base or pathlib.Path(__file__).parent.parent.parent) / DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    # one-time migration from legacy repo location
    try:
        legacy = pathlib.Path(__file__).parent.parent.parent / _LEGACY_DIR_NAME
        if legacy.exists() and legacy.resolve() != d.resolve():
            for child in list(legacy.iterdir()):
                dest = d / child.name
                if not dest.exists():
                    import shutil
                    if child.is_dir():
                        shutil.copytree(child, dest, dirs_exist_ok=True)
                    else:
                        shutil.move(str(child), str(dest))
    except Exception:
        pass
    return d

def _db(base: pathlib.Path) -> sqlite3.Connection:
    d = _base(base)
    db = sqlite3.connect(d / DB_FILE)
    db.execute("CREATE TABLE IF NOT EXISTS pages(slug TEXT PRIMARY KEY, title TEXT, body TEXT, created_at TEXT)")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(slug, title, body)")
    db.execute("CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY, fact TEXT, provenance TEXT, entity TEXT, kind TEXT, created_at TEXT)")
    return db

def remember(base: pathlib.Path, fact: str, provenance: str, entity: str = "people/me", kind: str = "fact") -> str:
    fact = fact.strip()
    assert provenance, "provenance required (Gbrain contract)"
    fid = hashlib.sha256(f"{fact}|{provenance}|{entity}".encode()).hexdigest()[:12]
    d = _base(base)
    # facts.jsonl
    row = {"id": fid, "fact": fact, "provenance": provenance, "entity": entity, "kind": kind, "created_at": datetime.datetime.utcnow().isoformat()}
    with open(d / FACTS_FILE, "a") as f:
        f.write(json.dumps(row) + "\n")
    # pages: one per entity (Gbrain page analogy)
    slug = entity.replace("/","-")
    page = d / f"{slug}.md"
    if not page.exists():
        page.write_text(f"# {entity}\n\n")
    txt = page.read_text()
    if fact not in txt:
        txt += f"- {fact} <!-- {provenance} {fid} -->\n"
        page.write_text(txt)
    # FTS
    db = _db(base)
    db.execute("REPLACE INTO pages(slug,title,body,created_at) VALUES(?,?,?,?)", (slug, entity, txt, row["created_at"]))
    db.execute("REPLACE INTO pages_fts(slug,title,body) VALUES(?,?,?)", (slug, entity, txt))
    db.execute("REPLACE INTO facts(id,fact,provenance,entity,kind,created_at) VALUES(?,?,?,?,?,?)", (fid, fact, provenance, entity, kind, row["created_at"]))
    db.commit(); db.close()
    # graph edge (zero-LLM deterministic)
    _extract_edges(base, fact, entity)
    return fid

def recall(base: pathlib.Path, query: str = "", entity: str = "", limit: int = 10) -> dict:
    d = _base(base)
    db = _db(base)
    facts = []
    if entity:
        cur = db.execute("SELECT id,fact,provenance,entity,kind,created_at FROM facts WHERE entity=? ORDER BY created_at DESC LIMIT ?", (entity, limit))
        facts = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
    elif query:
        # FTS first
        try:
            cur = db.execute("SELECT slug FROM pages_fts WHERE pages_fts MATCH ? LIMIT ?", (query, limit))
            slugs = [r[0] for r in cur.fetchall()]
            for slug in slugs:
                cur2 = db.execute("SELECT id,fact,provenance,entity FROM facts WHERE fact LIKE ? LIMIT 3", (f"%{query}%",))
                for r in cur2.fetchall():
                    facts.append({"id": r[0], "fact": r[1], "provenance": r[2], "entity": r[3]})
        except Exception:
            cur = db.execute("SELECT id,fact,provenance,entity FROM facts WHERE fact LIKE ? LIMIT ?", (f"%{query}%", limit))
            facts = [{"id": r[0], "fact": r[1], "provenance": r[2], "entity": r[3]} for r in cur.fetchall()]
    else:
        cur = db.execute("SELECT id,fact,provenance,entity,kind,created_at FROM facts ORDER BY created_at DESC LIMIT ?", (limit,))
        facts = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
    db.close()
    # results mirrors Gbrain results[] (evidence/FTS)
    return {"protocol_version": 1, "facts": facts, "total": len(facts), "results": [], "search_degraded": None}

def forget(base: pathlib.Path, fact_id: str) -> bool:
    d = _base(base)
    db = _db(base)
    db.execute("DELETE FROM facts WHERE id=?", (fact_id,))
    db.commit(); db.close()
    # rewrite facts.jsonl
    if (d / FACTS_FILE).exists():
        rows = [json.loads(l) for l in open(d / FACTS_FILE) if l.strip()]
        rows = [r for r in rows if r["id"] != fact_id]
        open(d / FACTS_FILE, "w").write("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))
    return True

def _extract_edges(base: pathlib.Path, fact: str, entity: str):
    # deterministic, zero-LLM (Gbrain graph style)
    patterns = [(r"works at (\w+)", "works_at"), (r"founded (\w+)", "founded"), (r"invested in (\w+)", "invested_in"), (r"attended (\w+)", "attended")]
    d = _base(base)
    for pat, rel in patterns:
        for m in re.finditer(pat, fact, re.I):
            edge = {"src": entity, "dst": m.group(1), "relation": rel, "fact": fact}
            with open(d / EDGES_FILE, "a") as f:
                f.write(json.dumps(edge)+"\n")
