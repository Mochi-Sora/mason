"""Short-term: 7 files, 3000 chars, bullet-only .md"""
import pathlib, datetime, re, json, hashlib, sqlite3

MAX_FILES = 7
MAX_CHARS = 3000
DIR_NAME = "short_term_memories"

def _dir(base: pathlib.Path) -> pathlib.Path:
    d = base / DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d

def _today() -> str:
    return datetime.date.today().isoformat()

def _extract_facts_mem0(text: str, llm_client=None) -> list[str]:
    """mem0-inspired ADD-only extraction — single LLM call, no UPDATE/DELETE
    Falls back to heuristic if 1B unavailable.
    """
    if llm_client is None:
        # heuristic: split on sentences, keep meaningful ones
        parts = [p.strip() for p in text.replace("—"," ").split(".") if len(p.strip())>12]
        return parts[:3] if parts else [text.strip()]
    from custom_memory.llm.tasks.extract_task import build_prompt as extract_prompt
    prompt = extract_prompt(text)
    try:
        raw = llm_client.complete(prompt, max_tokens=256, temperature=0.2)
        import re as _re
        m = _re.search(r"\[.*\]", raw, _re.S)
        if m:
            j = json.loads(m.group(0))
            if isinstance(j, list):
                return [str(x).strip() for x in j if str(x).strip()]
    except Exception:
        pass
    return [text.strip()]

def _dedup_check(base: pathlib.Path, new_fact: str, threshold: float = 0.85) -> bool:
    """mem0 dedup: check if fact already exists in last 7 files (Jaccard heuristic, no embedding needed for 1B path)
    Returns True if duplicate.
    """
    existing = recall(base).lower()
    # simple token overlap
    a = set(new_fact.lower().split())
    for line in existing.splitlines():
        b = set(line.lower().split())
        if not b: continue
        jacc = len(a & b) / len(a | b) if (a|b) else 0
        if jacc > threshold:
            return True
    return False

def _sanitize_bullet(text: str) -> str:
    text = text.strip()
    if not text.startswith("-"):
        text = "- " + text
    # ensure timestamp prefix if missing
    if not re.match(r"^- \d{2}:\d{2}", text):
        now = datetime.datetime.utcnow().strftime("%H:%M UTC — ")
        text = text.replace("- ", f"- {now}", 1)
    return text

def remember(base: pathlib.Path, text: str, date: str | None = None, llm_client=None) -> pathlib.Path:
    # mem0-inspired: extract then dedup, but still store as clean bullet (3000 char, 7-file cap preserved)
    facts = _extract_facts_mem0(text, llm_client)
    # write primary bullet (original) plus dedup check
    d = _dir(base)
    date = date or _today()
    p = d / f"{date}.md"
    bullet = _sanitize_bullet(text)
    # mem0 dedup: skip vector indexing if duplicate, but keep .md append for human readability
    is_dup = False
    for _f in facts:
        if _dedup_check(base, _f):
            is_dup = True
            break
    header = f"# {date}\n"
    existing = p.read_text() if p.exists() else header
    if not existing.startswith("#"):
        existing = header + existing
    # append bullet
    if not existing.endswith("\n"):
        existing += "\n"
    existing += bullet + "\n"
    # enforce 3000 char cap: keep header + newest bullets
    if len(existing) > MAX_CHARS:
        lines = existing.splitlines()
        header_line = lines[0]
        bullets = lines[1:]
        # keep newest until under cap
        kept = []
        cur = header_line + "\n"
        for b in reversed(bullets):
            if len(cur) + len(b) + 1 <= MAX_CHARS:
                kept.append(b)
            else:
                break
        kept.reverse()
        existing = header_line + "\n" + "\n".join(kept) + "\n"
        if len(existing) > MAX_CHARS:
            existing = existing[:MAX_CHARS-12] + "\n…(truncated)\n"
    p.write_text(existing)
    return p

def recall(base: pathlib.Path, days: int = 7) -> str:
    d = _dir(base)
    files = sorted(d.glob("*.md"))[-days:]
    out = []
    for f in reversed(files):
        out.append(f.read_text())
    return "\n".join(out)

def list_files(base: pathlib.Path):
    return sorted(_dir(base).glob("*.md"))

def prune(base: pathlib.Path, promoter=None) -> list[str]:
    """Enforce 7 files. Promote oldest via promoter(llm) if provided."""
    d = _dir(base)
    files = sorted(d.glob("*.md"))
    removed = []
    while len(files) > MAX_FILES:
        oldest = files[0]
        content = oldest.read_text()
        if promoter:
            try:
                result = promoter(content, oldest.name)
                # promoter handles long_term.remember internally
                print(f"[prune] promoter for {oldest.name}: {result}")
            except Exception as e:
                print(f"[prune] promoter error {oldest.name}: {e}")
        oldest.unlink()
        removed.append(oldest.name)
        files = sorted(d.glob("*.md"))
    return removed
