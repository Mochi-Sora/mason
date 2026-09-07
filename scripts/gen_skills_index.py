#!/usr/bin/env python3
"""Generate Mason's BUILT-IN skills index from first-party skills in-repo.

Mason is detached: no docs site serves skills-index.json. This walks
skills/*/*/SKILL.md frontmatter (name, description, tags) into
tools/skills_index_builtin.json, which MasonIndexSource uses as its FINAL
fallback (remote -> stale disk cache -> builtin). Hub search works offline
over everything Mason actually ships.

Usage: python scripts/gen_skills_index.py   (stdlib only)
Re-run when skills change.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        # bare KEY: value header (no --- fences), like mason-agent/SKILL.md
        head = []
        for line in text.splitlines():
            if not line.strip() or line.startswith("#"):
                if head:
                    break
                continue
            if ":" in line and not line.startswith((" ", "\t", "-", "|", ">")):
                head.append(line)
            elif head:
                break
        text = "---\n" + "\n".join(head) + "\n---\n"
    else:
        end = text.find("\n---", 3)
        if end < 0:
            return {}
        text = text[:end + 4]
    data: dict = {}
    current_key = ""
    for line in text.splitlines():
        if line.strip() in ("---", "..."):
            continue
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, val = line.partition(":")
            current_key = key.strip()
            data[current_key] = val.strip().strip('"').strip("'")
        elif current_key and line.strip().startswith("- "):
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(line.strip()[2:].strip())
    return data


def _tags(fm: dict, raw: str = "") -> list:
    import re
    m = re.search(r"tags:\s*\[([^\]]*)\]", raw)
    if m:
        return [t.strip().strip("\"'") for t in m.group(1).split(",") if t.strip().strip("\"'")]
    for key in ("tags",):
        val = fm.get(key)
        if isinstance(val, list):
            return [str(t) for t in val]
    return []


def main() -> None:
    skills = []
    for skill_md in sorted((REPO / "skills").rglob("SKILL.md")):
        try:
            raw = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _frontmatter(skill_md)
        name = str(fm.get("name", "") or skill_md.parent.name).strip()
        desc = str(fm.get("description", "") or "").strip()
        if not name:
            continue
        rel = skill_md.parent.relative_to(REPO).as_posix()
        skills.append({
            "name": name,
            "description": desc or f"Mason built-in skill: {name}.",
            "tags": _tags(fm, raw),
            "identifier": f"builtin/{name}",
            "source": "builtin",
            "trust_level": "official",
            "local_path": rel,
            "extra": {"provider": "mason"},
        })
    manifest = {"skills": skills,
                "note": "Mason built-in fallback — first-party skills in-repo, no network."}
    out = REPO / "tools" / "skills_index_builtin.json"
    out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"builtin skills index: {len(skills)} skills -> {out}")


if __name__ == "__main__":
    main()
