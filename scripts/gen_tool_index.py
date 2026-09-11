#!/usr/bin/env python3
"""Generate Mason's folder tool index: tools/index/{<name>.json, INDEX.md, summaries.json}.

The index is the searchable home of every tool schema. Runtime reads:
  - summaries.json overrides schema descriptions in the bridge manifest
    (tools/tool_search_catalog.py); the 1B model keeps these lines sharp
    (see tiered_memory/llm/tasks/tool_summary_task.py + nightly sweep).
  - <name>.json holds the full native schema for docs/diffing.

New tools: implement + register normally, re-run this script, done — they
auto-defer behind the bridge the moment they register (no config edit).

Usage: python scripts/gen_tool_index.py [--out tools/index]
Run with the project venv python (imports every tools/*.py module).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def _short(desc: str, max_chars: int = 100) -> str:
    text = " ".join((desc or "").split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(",;: ") + "…"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "tools" / "index"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from tools.registry import discover_builtin_tools, registry
    try:
        discover_builtin_tools()
    except Exception as e:
        print(f"discovery warnings (continuing): {e}")

    try:
        entries = registry.get_all_entries()
        names = sorted({e.name for e in entries if getattr(e, "name", "")})
    except Exception:
        names = []
    # Union the core list so the seed covers tools whose check_fn fails in THIS
    # env (missing optional deps) — their lines get refined by the 1B later.
    try:
        from toolsets import _MASON_CORE_TOOLS
        for _n in _MASON_CORE_TOOLS:
            if _n not in names:
                names.append(_n)
        names.sort()
    except Exception:
        pass

    summaries_path = out / "summaries.json"
    old_summaries = {}
    try:
        raw = json.loads(summaries_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            old_summaries = {str(k): str(v) for k, v in raw.items()}
    except Exception:
        pass

    summaries = dict(old_summaries)  # 1B-tuned lines win over regenerations
    index_rows = []
    for name in names:
        try:
            defs = registry.get_definitions({name}, quiet=True) or []
        except Exception:
            defs = []
        if not defs:
            # Registered but unavailable here (check_fn) or union-seeded:
            # keep the line so the manifest is complete; 1B refines later.
            summaries.setdefault(name, "Mason tool — load schema with tool_describe")
            index_rows.append((name, summaries[name]))
            continue
        td = defs[0]
        fn = (td.get("function") or {}) if isinstance(td, dict) else {}
        desc = str(fn.get("description", "") or "")
        (out / f"{name}.json").write_text(
            json.dumps(td, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        summaries.setdefault(name, _short(desc))
        index_rows.append((name, summaries[name]))

    summaries_path.write_text(
        json.dumps(dict(sorted(summaries.items())), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")

    lines = ["# Mason tool index", "",
             f"{len(index_rows)} tools. One line each — this is the model's search surface.",
             "Full schemas: `<name>.json`. Summaries: `summaries.json` (1B-maintained).", ""]
    for name, summary in sorted(index_rows):
        lines.append(f"- {name}: {summary}")
    (out / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"indexed {len(index_rows)} tools -> {out}")
    try:
        from tools.tool_search_catalog import refresh_summaries_cache
        refresh_summaries_cache()
    except Exception:
        pass


if __name__ == "__main__":
    main()
