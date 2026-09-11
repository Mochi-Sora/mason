"""Short-term: 7 files, 3000 chars, bullet-only .md"""
import pathlib, datetime, re, json, hashlib, sqlite3

MAX_FILES = 7
MAX_CHARS = 3000
DIR_NAME = "short_term_memories"
_LEGACY_DIR_NAME = DIR_NAME

def _dir(base: pathlib.Path | None = None) -> pathlib.Path:
    # primary: MASON_HOME/short_term_memories
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
            for child in list(legacy.glob("*.md")):
                dest = d / child.name
                if not dest.exists():
                    import shutil
                    shutil.move(str(child), str(dest))
    except Exception:
        pass
    return d

def _today() -> str:
    return datetime.date.today().isoformat()

def _extract_facts_mem0(text: str, llm_client=None) -> list[str]:
    """mem0-inspired ADD-only extraction — single LLM call, no UPDATE/DELETE
    Falls back to heuristic if 1B unavailable.
    """
    if llm_client is None:
        # heuristic: strip backup headers/timestamps/empty markers, keep real sentences
        cleaned = []
        for line in text.splitlines():
            line=line.strip()
            if not line or line.startswith("# Backup") or line.startswith("## "): 
                continue
            if line.startswith("- "): line=line[2:]
            # strip leading timestamp like "13:36 UTC — "
            import re as _re
            line=_re.sub(r"^\d{1,2}:\d{2} UTC —\s*", "", line)
            line=_re.sub(r"^\d{4}-\d{2}-\d{2}.*?:\s*", "", line)
            if len(line)>30 and any(c.isalpha() for c in line) and "8259" not in line:
                cleaned.append(line)
        # split remaining on sentences
        parts=[]
        for c in cleaned:
            for p in c.replace("—"," ").split("."):
                p=p.strip()
                if len(p)>30 and len(p.split())>4:
                    parts.append(p)
        return parts[:3] if parts else [c for c in cleaned[:1] if len(c)>20]
    from tiered_memory.llm.tasks.extract_task import build_prompt as extract_prompt
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
    # mem0-inspired: extract then dedup — skip write entirely if duplicate
    facts = _extract_facts_mem0(text, llm_client)
    d = _dir(base)
    # dedup: if any extracted fact already exists, skip this remember
    for _f in facts:
        if _dedup_check(base, _f):
            # return existing file without appending
            return d / f"{date or _today()}.md"
    date = date or _today()
    p = d / f"{date}.md"
    # use first clean fact as bullet, not raw transcript
    bullet_text = facts[0] if facts else text
    bullet = _sanitize_bullet(bullet_text)
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
