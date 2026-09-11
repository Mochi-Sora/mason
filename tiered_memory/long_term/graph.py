"""Graph helpers — deterministic edges, Gbrain-style"""
import pathlib, json

def list_edges(base: pathlib.Path, relation: str = "", entity: str = ""):
    p = base / "long_term_memories" / "edges.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    if relation:
        rows = [r for r in rows if r.get("relation")==relation]
    if entity:
        rows = [r for r in rows if r.get("src")==entity or r.get("dst")==entity]
    return rows
