# Tiered Memory — Design (Mason)

## Goals
Two-tier memory (mem0 short-term + Gbrain long-term) replacing Mason built-in:
- Short-term: 7-day rolling .md bullet journal (human-readable, bounded)
- Long-term: Gbrain-inspired durable store (no self-evolution/dream cycle)
- Evaluator: 1B local LLM via llama.cpp promotes expired short-term → long-term

## 1. Short-Term Memory (`tiered_memory/short_term/`)

**Path:** `~/.mason/short_term_memories/` (MASON_HOME, migrated from `~/custom-agent/short_term_memories/` legacy)
- One file per day: `YYYY-MM-DD.md` (e.g. `2026-09-06.md`)
- Format: clean markdown bullet points only:
  ```markdown
  # 2026-09-06
  - 10:32 UTC — user prefers dark mode in every editor
  - 14:11 UTC — discussed Mason strip plan, kept MCP/ACP
  ```
- Limit: **3000 chars per file** (hard cap). On overflow: newest bullets win, oldest truncated with `…(truncated)`.
- Cap: **7 files max**. On day 8, oldest file is evaluated for promotion before deletion.
- Writer: append-only `remember(text)` → today's file + timestamp.
- Reader: `recall(days=7)` → concat last 7 files in reverse chronological, for prompt injection.

**Promotion flow (day >7):**
```
oldest.md (e.g. 2026-08-30.md) → llama.cpp 1B prompt → JSON {promote: bool, facts: string[], reason: string}
if promote: → long_term.remember(facts, provenance="short-term:2026-08-30.md")
delete oldest.md
```

## 2. Long-Term Memory (`tiered_memory/long_term/`)
Inspired by **Gbrain** (garrytan/gbrain) — take ONLY memory architecture, ignore self-evolution:
- Gbrain core = Pages (markdown, frontmatter) + Facts (entity-linked, provenance) + Vectors (pgvector) + Graph edges (typed, zero-LLM)
- Our minimal faithful port:
  - Store: `long_term_memories/` markdown pages (one per entity/topic) + `long_term.db` SQLite FTS5 + `facts.jsonl` + `edges.jsonl` (deterministic, no LLM)
  - Facts: `facts.jsonl` per entity, each {fact, provenance, created_at, entity, kind}
  - Search: FTS5 keyword (keyword_exact evidence, budget-packed via recall_backup/recall); optional vector via ollama:nomic-embed-text if available
  - Graph: lightweight edges `edges.jsonl` — {src, dst, relation} extracted via deterministic regex (no LLM): `works_at`, `founded`, `invested_in`, `attended`
  - No dream cycle, no consolidation cron, no self-evolution — explicit promote only.
- Verbs (subset of Gbrain MEMORY_VERBS v1): `remember`, `recall`, `forget`, `synthesize` (LLM synthesis via local 1B or fallback to proxy)

## 3. Local LLM — llama.cpp global (`tiered_memory/llm/`)

**llama.cpp** is the global inference layer, not just memory:
- Binary: `llama.cpp` built from source or via `llama-cpp-python` (pip)
- Model: 1B GGUF — `Qwen/Qwen2-0.5B-Instruct-GGUF` or `TinyLlama-1.1B-Chat` (~600MB, fits VPS 11GiB)
- Server: `llama-server` on 127.0.0.1:8080 (OpenAI-compatible) OR direct `llama_cpp.Llama` Python binding
- Global config: `tiered_memory/llm/config.yaml` → {model_path, n_ctx 2048, n_threads 2, temp 0.2}
- Used by:
  - Short-term promoter (binary yes/no + fact extraction)
  - Long-term synthesizer (answer with citations)
  - Any agent turn that wants local inference (provider `local-llm`)

## 4. Integration with Custom Agent

Current status (lean, efficient):
- `tiered_memory/provider.py` implements `MemoryProvider` ABC (storage-complete: pages/facts/FTS/edges work).
- Not yet auto-wired as `memory.provider=custom` — cross-session recall today is `session_search` + short-term Recent Memory injection (last 7-day file, 1.5K). Wiring is one config line when wanted.
- Lifecycle: `sessions/manager.py:on_session_close` promotes backup→short-term (heuristic if 0.5B dormant, deduped), then purges session; `short_term/manager.py:prune()` enforces 7-file cap and promotes oldest→long-term via promoter.

## 5. File Layout

```
~/custom-agent/tiered_memory/
  short_term/manager.py  # 7×3000 char, heuristic fallback when 0.5B dormant
  long_term/store.py     # pages + facts.jsonl + FTS5 + edges.jsonl
  llm/client.py          # llama.cpp :8080 wrapper
  provider.py            # MemoryProvider (currently storage-complete, not auto-wired into prompt — cross-session recall via session_search/short_term preview)
~/.mason/short_term_memories/   # runtime (7×3000, promoted at close, injected as Recent Memory)
~/.mason/long_term_memories/    # runtime (Gbrain-style, provenance-tagged)
~/.mason/sessions/<id>/         # per-session state.md (<2K) + backup.md (10M) + backup.db FTS5
```

## 6. Operational guarantees
- 7 files hard limit — never 8
- 3000 chars hard limit — truncate oldest bullet
- Bullet-only — reject non-bullet writes (auto-prefix)
- Promotion is explicit + provenance-tagged
- llama.cpp fallback: if model missing, promoter returns {promote: false} (safe) and synthesizer falls back to keyword search


## 7. State history — the efficiency core (state-first O(1))
- `sessions/<id>/state.md` (<2K) auto-injected into prompt + current turn only = ~17 KB (was 60 KB with AGENTS.md chain + 4-turn window).
- `backup.md` (10M, append-only, FTS5 `backup.db`) holds full transcript, budget-packed via `recall_backup(query, budget_tokens=2000)`.
- `turn_tool_round.py` auto-distills `tool(args…) → outcome` into `state.md` (newest-kept, 2K cap) so state stays fresh even if model forgets `write_state`.
- Lazy: AGENTS.md 30K→2K stub + lazy skills index (35 built-in) keep the prompt cache-stable (89% hit).
