#!/usr/bin/env sh
# Mason one-line installer — Android / Termux
# Usage: curl -fsSL https://raw.githubusercontent.com/Mochi-Sora/Mason-Agent/main/scripts/install-termux.sh | sh
# What it does: pkg deps + uv + Python 3.11 + Mason (termux extra) + 400MB 0.5B — one line.

set -eu

REPO="Mochi-Sora/Mason-Agent"

echo "→ Termux detected — installing Mason (termux extra, 400MB model)..."
# Termux pkg deps (no sudo)
pkg update -y 2>/dev/null || true
pkg install -y python git curl ripgrep nodejs 2>/dev/null || pkg install -y python git curl 2>/dev/null || true

# uv
if ! command -v uv >/dev/null 2>&1; then
  echo "→ Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
for p in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
  case ":$PATH:" in *":$p:"*) ;; *) export PATH="$p:$PATH" ;; esac
done

# Mason — use [termux] extra (avoids Android-incompatible voice deps)
echo "→ Installing Mason..."
if ! uv python find 3.11 >/dev/null 2>&1; then
  uv python install 3.11 2>/dev/null || true
fi
# Try termux extra first
uv pip install "git+https://github.com/${REPO}.git#egg=mason-agent[termux]" --python 3.11 2>/dev/null || \
uv pip install "git+https://github.com/${REPO}.git" --python 3.11 2>/dev/null || \
pip install "git+https://github.com/${REPO}.git"

echo "→ Onboarding (400MB 0.5B, one-time)..."
if command -v mason >/dev/null 2>&1; then
  mason onboard --yes 2>/dev/null || mason onboard 2>/dev/null || echo "⚠ onboard needs network — re-run: mason onboard --yes"
else
  uv run mason onboard --yes 2>/dev/null || echo "⚠ mason not on PATH — re-run: mason onboard --yes"
fi

echo "✓ Done — run: mason"
echo "  mason              # chat"
echo "  mason prompt-size  # verify ~17KB"
