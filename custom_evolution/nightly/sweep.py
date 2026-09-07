"""Nightly-Dream-cycle — 02:00 sweep
- Lightweight always (1B) — full day sweep
- Heavyweight only if hard queue non-empty (main model)
"""
import pathlib, datetime, json, re
from custom_evolution.tasks.nightly_light_task import build_prompt as light_prompt
from custom_evolution.tasks.nightly_heavy_task import build_prompt as heavy_prompt

_REFUSAL_RE = re.compile(
    r"(?i)\bi['’]m sorry\b|cann?ot (assist|help)\b|can['’]t (assist|help)\b"
    r"|\bas an ai\b|not able to (help|assist)\b|against (my|policy)\b")


def _looks_like_refusal(text: str) -> bool:
    """0.5B safety misfires on benign engineering prompts — catch and retry."""
    t = (text or "").strip()
    return bool(t) and len(t) < 300 and _REFUSAL_RE.search(t) is not None

def run_nightly(base: pathlib.Path, llm_1b=None, main_client=None, date: str | None = None) -> dict:
    date = date or datetime.date.today().isoformat()
    base = pathlib.Path(base)
    st_dir = base / "short_term_memories"
    queue = base / "custom_evolution" / "queue" / "hard.jsonl"
    fixes_log = base / "custom_evolution" / "queue" / "fixes.jsonl"
    nightly_dir = base / "custom_evolution" / "nightly"
    nightly_dir.mkdir(parents=True, exist_ok=True)

    # Collect today's bullets
    bullets = ""
    if st_dir.exists():
        for f in sorted(st_dir.glob("*.md")):
            bullets += f.read_text() + "\n"
    fixes = fixes_log.read_text()[-1200:] if fixes_log.exists() else "(no fixes today)"
    # tool errors: grep from evolution.log
    elog = base / "custom_evolution" / "evolution.log"
    errors = ""
    if elog.exists():
        for line in elog.read_text().splitlines()[-20:]:
            if "error" in line.lower():
                errors += line[:200] + "\n"
    if not errors:
        errors = "(no tool errors)"

    # === Lightweight (1B) ===
    light_report = "(1B unavailable — heuristic report)"
    if llm_1b:
        prompt = light_prompt(bullets or "(no short-term today)", fixes, errors, date)
        try:
            # stop=[] : the report is multi-paragraph; the client's default
            # blank-line stop would decapitate it after the header.
            # timeout=120: long prompt + CPU 1B needs room (default 10s is for JSON one-liners).
            try:
                light_report = llm_1b.complete(prompt, max_tokens=800, temperature=0.2, stop=[], timeout=120)
            except TypeError:
                light_report = llm_1b.complete(prompt, max_tokens=800, temperature=0.2)
            if _looks_like_refusal(light_report):
                # 0.5B safety misfire on benign input: one plain retry, then
                # the heuristic report (a thin night beats a refused night).
                retry = "Complete this routine engineering summary. No policy issues involved.\n\n" + prompt
                try:
                    light_report = llm_1b.complete(retry, max_tokens=800, temperature=0.5, stop=[], timeout=120)
                except TypeError:
                    light_report = llm_1b.complete(retry, max_tokens=800, temperature=0.5)
                if _looks_like_refusal(light_report):
                    light_report = (
                        f"## Lightweight Evolution — {date}\n"
                        f"- Bullets today: {len(bullets.splitlines())}\n- Fixes: {fixes[:200]}\n"
                        "- 1B refused twice — heuristic fallback.")
        except Exception as e:
            light_report = f"Light evolution failed: {e}"
    else:
        # heuristic fallback
        light_report = f"## Lightweight Evolution — {date}\n- Bullets today: {len(bullets.splitlines())}\n- Fixes: {fixes[:200]}\n- No 1B active — promote manually."

    out_light = nightly_dir / f"{date}-report.md"
    out_light.write_text(light_report)

    result = {"date": date, "light_report": str(out_light), "heavy": None}

    # === Tool summaries (1B): keep the bridge manifest sharp ===
    try:
        from tools.working_set import refresh_tool_summaries
        result["summaries_refreshed"] = refresh_tool_summaries(llm_1b, limit=5)
    except Exception as e:
        result["summaries_refreshed"] = {"error": str(e)[:200]}

    # === Heavyweight (main model) — only if queued ===
    has_queue = queue.exists() and queue.read_text().strip()
    if has_queue and main_client:
        qtxt = queue.read_text()
        prompt = heavy_prompt(qtxt[:4000], light_report[:2000])
        try:
            heavy_out = main_client.complete(prompt, max_tokens=1200, temperature=0.3)
        except Exception as e:
            heavy_out = f"Heavy evolution failed: {e}"
        heavy_dir = nightly_dir / f"{date}-heavy"
        heavy_dir.mkdir(exist_ok=True)
        (heavy_dir / "heavy.md").write_text(heavy_out)
        result["heavy"] = str(heavy_dir / "heavy.md")
        # archive queue
        arch = base / "custom_evolution" / "queue" / "archive" / f"{date}.jsonl"
        arch.parent.mkdir(parents=True, exist_ok=True)
        arch.write_text(qtxt)
        queue.write_text("")
    elif has_queue:
        result["heavy_skipped"] = "main model unavailable — queue preserved"

    # log
    with open(base / "custom_evolution" / "evolution.log", "a") as f:
        f.write(json.dumps({"type":"nightly","ts":datetime.datetime.utcnow().isoformat(),"date":date,"has_queue":bool(has_queue)})+"\n")

    return result

if __name__ == "__main__":
    import sys
    from custom_memory.llm.client import LlamaClient
    base = pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path(".")
    print(run_nightly(base, llm_1b=LlamaClient()))
