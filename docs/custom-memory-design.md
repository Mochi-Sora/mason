# Custom Memory System — Design (Custom Agent)

## Goals
Replace Mason built-in memory with a 2-tier system:
- Short-term: 7-day rolling .md bullet journal (human-readable, bounded)
- Long-term: Gbrain-inspired durable store (no self-evolution/dream cycle)
- Evaluator: 1B local LLM via llama.cpp promotes expired short-term → long-term

## 1. Short-Term Memory (`custom_memory/short_term/`)

**Path:** `~/.custom-agent/short_term_memories/` (and `~/custom-agent/short_term_memories/` for template)
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

## 2. Long-Term Memory (`custom_memory/long_term/`)
Inspired by **Gbrain** (garrytan/gbrain) — take ONLY memory architecture, ignore self-evolution:
- Gbrain core = Pages (markdown, frontmatter) + Facts (entity-linked, provenance) + Vectors (pgvector) + Graph edges (typed, zero-LLM)
- Our minimal faithful port:
  - Store: `long_term_memories/` markdown pages (one per entity/topic) + `long_term.db` SQLite (FTS5 + vector stub)
  - Facts: `facts.jsonl` per entity, each {fact, provenance, created_at, entity, kind}
  - Search: FTS5 keyword (tsvector analogue) + optional vector via ollama:nomic-embed-text (768d) if available, RRF fusion
  - Graph: lightweight edges `edges.jsonl` — {src, dst, relation} extracted via deterministic regex (no LLM): `works_at`, `founded`, `invested_in`, `attended`
  - No dream cycle, no consolidation cron, no self-evolution — explicit promote only.
- Verbs (subset of Gbrain MEMORY_VERBS v1): `remember`, `recall`, `forget`, `synthesize` (LLM synthesis via local 1B or fallback to proxy)

## 3. Local LLM — llama.cpp global (`custom_memory/llm/`)

**llama.cpp** is the global inference layer, not just memory:
- Binary: `llama.cpp` built from source or via `llama-cpp-python` (pip)
- Model: 1B GGUF — `Qwen/Qwen2-0.5B-Instruct-GGUF` or `TinyLlama-1.1B-Chat` (~600MB, fits VPS 11GiB)
- Server: `llama-server` on 127.0.0.1:8080 (OpenAI-compatible) OR direct `llama_cpp.Llama` Python binding
- Global config: `custom_memory/llm/config.yaml` → {model_path, n_ctx 2048, n_threads 2, temp 0.2}
- Used by:
  - Short-term promoter (binary yes/no + fact extraction)
  - Long-term synthesizer (answer with citations)
  - Any agent turn that wants local inference (provider `local-llm`)

## 4. Integration with Custom Agent

Replace `agent/memory_provider.py`:
- New provider `custom_memory/provider.py` implements `MemoryProvider` ABC
- Registers as `custom` in `agent/memory_manager.py`
- Config: `memory.provider: custom` in `config.yaml`
- Lifecycle: `init` creates folders, `remember` writes short-term, nightly `prune()` handles promotion

## 5. File Layout

```
~/custom-agent/custom_memory/
  __init__.py
  short_term/
    manager.py      # 7-file rolling, 3000 char cap
    promoter.py     # llama.cpp evaluator
  long_term/
    store.py        # pages + facts + FTS
    graph.py        # edge extraction
    synthesize.py   # long-term Q&A
  llm/
    client.py       # llama.cpp wrapper (server or python binding)
    config.yaml
    models/         # GGUF 1B
  provider.py       # MemoryProvider ABC impl
  config.py
~/custom-agent/short_term_memories/   # runtime (gitignored)
~/custom-agent/long_term_memories/    # runtime
```

## 6. Operational guarantees
- 7 files hard limit — never 8
- 3000 chars hard limit — truncate oldest bullet
- Bullet-only — reject non-bullet writes (auto-prefix)
- Promotion is explicit + provenance-tagged
- llama.cpp fallback: if model missing, promoter returns {promote: false} (safe) and synthesizer falls back to keyword search
