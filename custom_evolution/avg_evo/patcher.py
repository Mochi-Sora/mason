"""Micro-patcher for low/med Avg-evo fixes — applies without main model"""
import pathlib, json

def apply_pending(base: pathlib.Path, dry_run=True) -> list[str]:
    pending = list((base / "custom_evolution" / "patches" / "pending").glob("*.json"))
    applied = []
    for p in pending:
        j = json.loads(p.read_text())
        # Currently dry-run: just log, future hook can patch skills/prompts
        applied.append(f"{p.name}: {j.get('issue',{}).get('fix','')}")
        if not dry_run:
            p.unlink()
    return applied
