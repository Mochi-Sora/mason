# Self-Evolution — Avg-evo + Nightly-Dream-cycle (Custom Agent)

## Principles (not Gbrain)
- No Gbrain dream/consolidation. This is bespoke: per-response 1B fixes + nightly sweep.
- 1B local LLM (llama.cpp) is the default worker. Main model only for queued hard problems at night (heavyweight).
- Evolution mutates the *framework* (skills, prompts, memory, tool wrappers) — never silently mutates user data. All patches are diffs + reviewable.

## 1. Avg-evo — per-response lightweight evolution

**Trigger:** every time `agent/conversation_loop.py` returns `final_response` (including tool-call turns that produced user-facing text).

**Input to 1B:**
- `user_msg` (last user turn)
- `assistant_final` (what agent just said)
- `tool_trace` (last 3 tool results, truncated to 500 chars each)
- `memory_context` (short-term preview)

**1B prompt (deterministic JSON):**
```
You are a fixer. Analyze this agent response for problems.
Response: {assistant_final}
Tool trace: {tool_trace}
Return JSON: {"issues": [{"type":"error|inaccuracy|format|missing_ctx","severity":"low|med|high","fix":"one-line patch instruction"}], "hard_problem": {"queued": bool, "title": str, "reason": str} }
- high severity or needs reasoning >1B → hard_problem.queued=true
```

**Actions:**
- `issues` with severity low/med → apply immediately via patch queue: `custom_evolution/patches/pending/*.jsonl` → `agent/patch_applier.py` applies skill/prompt/memory micro-fixes (char-level, no main model).
- `hard_problem.queued=true` → push to `custom_evolution/queue/hard.jsonl` (title, reason, context snapshot). Avg-evo never calls main model.
- Latency budget: <800ms via llama.cpp (1B, temp 0.2, max 256 tokens). Fire-and-forget — never blocks user response delivery. User sees final_response first, fixes land next turn or nightly.

**Storage:**
```
custom_evolution/
  avg_evo/
    analyzer.py      # 1B call
    patcher.py       # micro-patches
  queue/
    hard.jsonl       # hard problems (avg-evo → nightly)
    fixes.jsonl      # applied fixes log
```

## 2. Nightly-Dream-cycle — nightly sweep

**Trigger:** cron `0 2 * * *` (2am local) or manual `python -m custom_evolution.nightly`.

**Input:** full day's `short_term_memories/YYYY-MM-DD.md` + `queue/hard.jsonl` + `avg_evo` fix log + `long_term_memories/facts.jsonl` delta.

**Two tiers:**
- **Lightweight (always, 1B):** sweep all short-term bullets + tool errors + low/med fixes that weren't applied. Generates `evolution_report.md` with: deduped learnings, prompt tweaks, skill patch proposals (diffs). Cost: ~2k tokens via 1B, <30s.
- **Heavyweight (only if queue non-empty, main model):** for each `hard.jsonl` entry, call main model (via `opencode-free` proxy at 127.0.0.1:8765 or configured provider) with full context to produce high-level evolution: new skill draft, architecture refactor plan, or long-term memory consolidation. Output → `custom_evolution/nightly/heavy/*.md`. Then clear queue (archive to `queue/archive/YYYY-MM-DD.jsonl`).

**Output:**
```
custom_evolution/nightly/
  2026-09-06-report.md       # lightweight report (1B)
  2026-09-06-heavy/          # heavyweight outputs (main model, only if queued)
  evolution.log              # append-only
```

## 3. Global 1B wiring

- Single `LlamaClient` from `custom_memory/llm/client.py` — reused for memory promoter, Avg-evo, nightly lightweight.
- Configurable via `custom_evolution/config.yaml`: `avg_evo.enabled, nightly.hour, heavyweight.model`.

## 4. Safety

- No auto-delete of user memories — evolution only proposes patches, writes to `patches/pending/` for review. Nightly heavyweight drafts are *proposals* in `custom_evolution/nightly/` — human or `curator` approves.
- Hard queue is bounded: max 50 entries; oldest dropped with log.
- All evolution runs are logged: `custom_evolution/evolution.log` (JSONL).
