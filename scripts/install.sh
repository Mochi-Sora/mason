#!/usr/bin/env sh
# Mason one-line installer — Linux / macOS / WSL2
# Usage: curl -fsSL https://raw.githubusercontent.com/Mochi-Sora/Mason-Agent/main/scripts/install.sh | sh
# What it does: uv + Python 3.11 + Mason + 400MB Qwen2-0.5B (llama-server :8080) — one line, no extra steps.
set -eu

REPO="Mochi-Sora/Mason-Agent"
MASON_HOME="${MASON_HOME:-$HOME/.mason}"

info() { printf "\033[1;34m→ %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m⚠ %s\033[0m\n" "$*"; }

# 1. uv (Rust package manager) — if missing
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  export PATH="$HOME/.cargo/bin:$PATH"
fi

# Ensure uv on PATH for this shell
for p in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
  case ":$PATH:" in *":$p:"*) ;; *) export PATH="$p:$PATH" ;; esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found after install — add \$HOME/.local/bin to PATH and re-run" >&2
  exit 1
fi

# 2. Python 3.11 via uv (no system python needed)
if ! uv python find 3.11 >/dev/null 2>&1; then
  info "Installing Python 3.11..."
  uv python install 3.11
fi

# 3. Mason (no git clone — pip from GitHub, venv auto-managed by uv)
info "Installing Mason..."
# Prefer pip install from git; falls back to local checkout if already cloned
if [ -d "./mason" ] && [ -f "./mason/pyproject.toml" ]; then
  uv pip install -e "./mason" --python 3.11 2>/dev/null || uv pip install -e "." --python 3.11
else
  uv pip install "git+https://github.com/${REPO}.git" --python 3.11 2>/dev/null || \
  uv tool install "mason-agent @ git+https://github.com/${REPO}.git" --python 3.11 2>/dev/null || \
  pip install "git+https://github.com/${REPO}.git"
fi

# Ensure mason on PATH (uv tool)
for p in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
  case ":$PATH:" in *":$p:"*) ;; *) export PATH="$p:$PATH" ;; esac
done

# 4. Onboard — downloads 400MB Qwen2-0.5B GGUF + writes ~/.mason/config.yaml + smoke-tests :8080
#    --yes = non-interactive, fetches model from HuggingFace (one-time 400MB, resumable)
info "Onboarding (fetching 400MB 0.5B model — one-time, may take a minute)..."
if command -v mason >/dev/null 2>&1; then
  mason onboard --yes || mason onboard || warn "onboard needs network for 400MB model — re-run: mason onboard --yes"
else
  # try uv run
  uv run mason onboard --yes 2>/dev/null || warn "mason not on PATH yet — open a new shell and run: mason onboard --yes"
fi

ok "Done — run: mason"
echo "  mason              # chat"
echo "  mason gateway      # Telegram/Discord"
echo "  mason prompt-size  # verify ~17KB O(1) prompt"
