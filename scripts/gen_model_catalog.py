#!/usr/bin/env python3
"""Generate Mason's BUILT-IN model catalog from in-repo provider metadata.

Mason is detached: no docs site serves model-catalog.json. This bakes the
checked-in provider/model tables (mason_cli.models._PROVIDER_MODELS +
agent.model_metadata.DEFAULT_CONTEXT_LENGTHS) into
mason_cli/model_catalog_builtin.json, which get_catalog() uses as its FINAL
fallback (remote -> disk cache -> builtin). Offline-first, never empty.

Usage: python scripts/gen_model_catalog.py   (run with the project venv python)
Re-run when provider tables change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def _context_for(model_id: str, table: dict) -> int | None:
    mid = model_id.lower()
    best, best_len = None, -1
    for key, ctx in table.items():
        k = str(key).lower()
        if k and k in mid and len(k) > best_len:
            best, best_len = int(ctx), len(k)
    return best


def main() -> None:
    from mason_cli.models import _PROVIDER_MODELS
    from agent.model_metadata import DEFAULT_CONTEXT_LENGTHS

    providers: Dict[str, Dict[str, Any]] = {}
    for provider, models in _PROVIDER_MODELS.items():
        if not isinstance(models, (list, tuple)):
            continue
        entries: List[Dict[str, Any]] = []
        for m in models:
            mid = m if isinstance(m, str) else str((m or {}).get("id", ""))
            mid = mid.strip()
            if not mid:
                continue
            ctx = _context_for(mid, DEFAULT_CONTEXT_LENGTHS)
            entry = {"id": mid}
            if ctx:
                entry["context"] = ctx
            entries.append(entry)
        if entries:
            providers[str(provider)] = {"models": entries}

    manifest = {"version": 1, "providers": providers,
                "note": "Mason built-in fallback — generated from in-repo tables, no network."}
    out = REPO / "mason_cli" / "model_catalog_builtin.json"
    out.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    n_models = sum(len(v["models"]) for v in providers.values())
    print(f"builtin catalog: {len(providers)} providers, {n_models} models -> {out}")


if __name__ == "__main__":
    main()
