<p align="center">
  <img src="assets/mason-logo.svg" alt="Mason" width="160">
</p>

# Mason ◈
> Detached fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research (MIT) — rebranded, stripped to core, and rebuilt with custom memory (mem0 short-term + Gbrain-style long-term), per-session state history, and nightly self-evolution. Contains no upstream remote: set your own.

**The self-improving AI agent, state-first edition.** It creates skills from experience, improves them during use, keeps a tiny per-session state (90% context cut) with an indexed backup it can search instantly, and runs a nightly evolution sweep. Run it on a $5 VPS, a GPU cluster, or serverless infrastructure that costs nearly nothing when idle. Talk to it from Telegram while it works on a cloud VM.

Use any model you want — OpenRouter, OpenAI, your own endpoint, and many others. Switch with `mason model` — no code changes, no lock-in.

<table>
<tr><td><b>A state-first terminal UI</b></td><td>Minimal Ink TUI showing the tiny state.md, backup stats and short-term health, with live chat wired through tui/bridge.py into the real agent loop (/recall, /state, /close).</td></tr>
<tr><td><b>Lives where you do</b></td><td>Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process. Voice memo transcription, cross-platform conversation continuity.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall. <a href="https://github.com/plastic-labs/honcho">Honcho</a> dialectic user modeling. Compatible with the <a href="https://agentskills.io">agentskills.io</a> open standard.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with delivery to any platform. Daily reports, nightly backups, weekly audits — all in natural language, running unattended.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Seven terminal backends — local, Docker, SSH, Singularity, Modal, Daytona, and Vercel Sandbox. Daytona and Modal offer serverless persistence — your agent's environment hibernates when idle and wakes on demand, costing nearly nothing between sessions. Run it on a $5 VPS or a GPU cluster.</td></tr>
<tr><td><b>Research-ready</b></td><td>Batch trajectory generation, trajectory compression for training the next generation of tool-calling models.</td></tr>
</table>

---

## Quick Install

### Linux, macOS, WSL2

```bash
git clone https://github.com/Mochi-Sora/mason.git && cd mason
python -m venv .venv && source .venv/bin/activate
pip install -e "."
mason onboard            # checks deps, prints what's missing + how to fix
mason onboard --yes      # also downloads the ~400MB 1B model (HuggingFace)
mason                    # start chatting!
```

`mason onboard` is the installer UX: it verifies Python ≥3.11, git, ripgrep,
node, llama-server, the 1B GGUF, and the TUI deps, writes a minimal
`~/.mason/config.yaml` if you have none, and finishes with a real 1B smoke
test. `--check-only` reports without writing anything. No API keys needed —
the default brain is local (llama-server on :8080).

For the server side you need `llama-server` on PATH: `brew install llama.cpp`
(macOS) or your distro package (`llama.cpp` on Arch), then run it in the
background: `llama-server -m custom_memory/llm/models/qwen2-0_5b-instruct-q4_k_m.gguf --port 8080`.
For the Ink TUI: `cd tui && npm install` (checked by onboard).

### Windows (native, PowerShell)

> **Heads up:** Native Windows runs Mason without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux/macOS instructions above work there too.

Run this in PowerShell (with `$env:MASON_REPO_URL` set to your Mason remote):

```powershell
git clone $env:MASON_REPO_URL; cd mason
.\scripts\install.ps1
```

The installer handles everything: uv, Python 3.11, Node.js, ripgrep, ffmpeg, **and a portable Git Bash** (MinGit, unpacked to `%LOCALAPPDATA%\mason\git` — no admin required, completely isolated from any system Git install). Mason uses this bundled Git Bash to run shell commands.

If you already have Git installed, the installer detects it and uses that instead. Otherwise a ~45MB MinGit download is all you need — it won't touch or interfere with any system Git.

> **Android / Termux:** On Termux, Mason installs a curated `.[termux]` extra because the full `.[all]` extra currently pulls Android-incompatible voice dependencies.
>
> **Windows:** Native Windows is fully supported — the PowerShell one-liner above installs everything. If you'd rather use WSL2, the Linux command works there too. Native Windows install lives under `%LOCALAPPDATA%\mason`; WSL2 installs under `~/.mason` as on Linux.

After installation:

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
mason              # start chatting!
```

### Troubleshooting

#### Windows Defender or antivirus flags `uv.exe` as malware

If your antivirus (Bitdefender, Windows Defender, etc.) quarantines `uv.exe` from the Mason `bin` folder (`%LOCALAPPDATA%\mason\bin\uv.exe`), this is a **false positive**. The file is Astral's `uv` — the Rust Python package manager Mason bundles to manage its Python environment. ML-based antivirus engines commonly flag unsigned Rust binaries that download and install packages.

**To verify your copy is authentic:**

```powershell
# Install GitHub CLI if needed
winget install --id GitHub.cli

# Login to GitHub
gh auth login

# Run verification
$uv = "$env:LOCALAPPDATA\mason\bin\uv.exe"
$ver = (& $uv --version).Split(' ')[1]
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$zip = "$env:TEMP\uv.zip"
Invoke-WebRequest "https://github.com/astral-sh/uv/releases/download/$ver/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip -UseBasicParsing
gh attestation verify $zip --repo astral-sh/uv
Expand-Archive $zip "$env:TEMP\uv_x" -Force
(Get-FileHash "$env:TEMP\uv_x\uv.exe").Hash -eq (Get-FileHash $uv).Hash
```

If attestation says "Verification succeeded" and the last line prints `True`, you're good.

**To whitelist Mason:**
- **Windows Defender:** Run PowerShell as Admin → `Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\mason\bin"`
- **Bitdefender:** Add an exception in the Bitdefender console (Protection > Antivirus > Settings > Manage Exceptions)
- Whitelist the **folder**, not the file hash — Mason updates `uv` and the hash changes every version

For more context, see the upstream Astral reports: [astral-sh/uv#13553](https://github.com/astral-sh/uv/issues/13553), [astral-sh/uv#15011](https://github.com/astral-sh/uv/issues/15011), [astral-sh/uv#10079](https://github.com/astral-sh/uv/issues/10079).

---

## Getting Started

```bash
mason              # Interactive CLI — start a conversation
mason model         # Choose your LLM provider and model
mason tools         # Configure which tools are enabled
mason config set   # Set individual config values
mason config get   # Print individual config values
mason gateway      # Start the messaging gateway (Telegram, Discord, etc.)
mason setup        # Run the full setup wizard (configures everything at once)
mason claw migrate # Migrate from OpenClaw (if coming from OpenClaw)
mason update       # Update to the latest version
mason doctor       # Diagnose any issues
```

📖 **Docs: this README + `mason --help` + `tools/index/INDEX.md`. No docs site on a detached fork.**

---

## CLI vs Messaging Quick Reference

Mason has two entry points: start the terminal UI with `mason`, or run the gateway and talk to it from Telegram, Discord, Slack, WhatsApp, Signal, or Email. Once you're in a conversation, many slash commands are shared across both interfaces.

| Action                         | CLI                                           | Messaging platforms                                                              |
| ------------------------------ | --------------------------------------------- | -------------------------------------------------------------------------------- |
| Start chatting                 | `mason`                                      | Run `mason gateway setup` + `mason gateway start`, then send the bot a message |
| Start fresh conversation       | `/new` or `/reset`                            | `/new` or `/reset`                                                               |
| Change model                   | `/model [provider:model]`                     | `/model [provider:model]`                                                        |
| Set a personality              | `/personality [name]`                         | `/personality [name]`                                                            |
| Retry or undo the last turn    | `/retry`, `/undo`                             | `/retry`, `/undo`                                                                |
| Compress context / check usage | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]`                                        |
| Browse skills                  | `/skills` or `/<skill-name>`                  | `/<skill-name>`                                                                  |
| Interrupt current work         | `Ctrl+C` or send a new message                | `/stop` or send a new message                                                    |
| Platform-specific status       | `/platforms`                                  | `/status`, `/sethome`                                                            |

For the full command lists, run `mason --help` and `mason <command> --help`.

---

## Documentation

No docs site on a detached fork — the repo is the docs:

| Where | What |
|---|---|
| This README | Install, ops checklist, command map |
| `tools/index/INDEX.md` | Every tool, one line each (regenerate: `scripts/gen_tool_index.py`) |
| `skills/autonomous-ai-agents/mason-agent/` | What Mason knows about itself (hub + routing) |
| `AGENTS.md` + `agent/` `mason_cli/` `tools/` `gateway/` `cron/` `skills/` `AGENTS.md` | Contributor internals per area |
| `docs/custom-memory-design.md` | Custom memory/evolution/state design |
| `mason --help`, `mason <command> --help` | Full command reference |

---

## Migrating from OpenClaw

If you're coming from OpenClaw, Mason can automatically import your settings, memories, skills, and API keys.

**During first-time setup:** The setup wizard (`mason setup`) automatically detects `~/.openclaw` and offers to migrate before configuration begins.

**Anytime after install:**

```bash
mason claw migrate              # Interactive migration (full preset)
mason claw migrate --dry-run    # Preview what would be migrated
mason claw migrate --preset user-data   # Migrate without secrets
mason claw migrate --overwrite  # Overwrite existing conflicts
```

What gets imported:

- **SOUL.md** — persona file
- **Memories** — MEMORY.md and USER.md entries
- **Skills** — user-created skills → `~/.mason/skills/openclaw-imports/`
- **Command allowlist** — approval patterns
- **Messaging settings** — platform configs, allowed users, working directory
- **API keys** — allowlisted secrets (Telegram, OpenRouter, OpenAI, Anthropic, ElevenLabs)
- **TTS assets** — workspace audio files
- **Workspace instructions** — AGENTS.md (with `--workspace-target`)

See `mason claw migrate --help` for all options, or use the `openclaw-migration` skill for an interactive agent-guided migration with dry-run previews.

---

## Contributing

We welcome contributions! House rules live in `AGENTS.md` (root + per-area files).

Quick start for contributors — clone, install, test from the checkout:

```bash
git clone <your-mason-remote> && cd mason
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

Manual clone fallback (for throwaway clones/CI where you intentionally do not
want the managed install layout):

Create the venv outside the cloned source tree — a venv inside the directory
the agent operates from can be wiped by a relative-path command the agent runs
against its own checkout, destroying the running runtime mid-session.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv ~/.mason/venvs/mason-dev --python 3.11
source ~/.mason/venvs/mason-dev/bin/activate
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

---

## Mason ops (first-run checklist)

```bash
# 1. Local 1B sidecar (memory, evolution, predictions) — direct llama.cpp:
#    drop any qwen2-0_5b GGUF into custom_memory/llm/models/, then:
systemctl --user enable --now mason-1b   # unit shipped in scripts/ (port 8080)
#    Alt backend (ollama): export MASON_1B_URL=http://127.0.0.1:11434 MASON_1B_MODEL=qwen2:0.5b

# 2. Regenerate the shipped indexes after pulling new tools/skills/models:
python scripts/gen_tool_index.py      # tools/index/ (bridge manifest source)
python scripts/gen_skills_index.py    # tools/skills_index_builtin.json (offline hub)
python scripts/gen_model_catalog.py   # mason_cli/model_catalog_builtin.json (offline picker)

# 3. Wake word: sherpa open-vocab "hey mason" is the default (zero training).
#    Legacy openWakeWord weights in tools/wakewords/ are NOT true mason detectors;
#    retrain with: python scripts/train_wakeword.py --positive data/positive --negative data/negative

# 4. Nightly evolution (02:00 recommended):
0 2 * * * cd ~/custom-agent && python custom_evolution/nightly/sweep.py .

# 5. State lives in ~/.mason (profiles: ~/.mason/profiles/<name>).
#    Per-profile warm tool sets: ~/.mason/working_sets.json (auto-maintained).

# 6. TUI (live loop): set your main model via MASON_PROVIDER/MODEL/BASE_URL/API_KEY, then:
cd tui && npm install && MASON_PROVIDER=openai MASON_MODEL=<your-model> \
  MASON_BASE_URL=<your-base-url> MASON_API_KEY=<your-key> npm start
# (No models ship with Mason — the 1B sidecar above is the only local weight,
#  and even that is gitignored. Main model is always yours.)
```

Cold start per turn ≈ clarify + 3 bridge tools + name list (~1.7k tok).
Everything else loads on describe and stays native via the working set.

---

## License

MIT — see [LICENSE](LICENSE).

Detached fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research (MIT).
