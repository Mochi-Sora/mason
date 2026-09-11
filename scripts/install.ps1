## Mason one-line installer — Native Windows (PowerShell)
# Usage: irm https://raw.githubusercontent.com/Mochi-Sora/mason/main/scripts/install.ps1 | iex
# What it does: uv + Python 3.11 + Mason + 400MB Qwen2-0.5B — one line, no admin, no manual llama-server.

$ErrorActionPreference = "Stop"
$Repo = "Mochi-Sora/mason"
$MasonHome = if ($env:MASON_HOME) { $env:MASON_HOME } else { Join-Path $env:LOCALAPPDATA "mason" }

function Info($m) { Write-Host "→ $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "✓ $m" -ForegroundColor Green }
function Warn($m) { Write-Host "⚠ $m" -ForegroundColor Yellow }

# 1. uv — download if missing (portable, no admin)
$uvBin = Join-Path $MasonHome "bin\uv.exe"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  if (Test-Path $uvBin) { $env:PATH = "$(Split-Path $uvBin);$env:PATH" }
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Info "Installing uv..."
  $uvVer = "0.7.13" # pinned, matches pyproject upper bound
  $zip = "$env:TEMP\uv.zip"
  $url = "https://github.com/astral-sh/uv/releases/download/$uvVer/uv-x86_64-pc-windows-msvc.zip"
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest $url -OutFile $zip -UseBasicParsing
  $dst = Join-Path $MasonHome "bin"
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Expand-Archive $zip $env:TEMP\uv_x -Force
  Copy-Item "$env:TEMP\uv_x\uv.exe" $uvBin -Force
  Copy-Item "$env:TEMP\uv_x\uvx.exe" (Join-Path $dst "uvx.exe") -Force -ErrorAction SilentlyContinue
  $env:PATH = "$dst;$env:PATH"
  # Persist for next shell
  $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
  if ($userPath -notlike "*$dst*") {
    [Environment]::SetEnvironmentVariable("PATH", "$dst;$userPath", "User")
  }
}

# 2. Python 3.11 + Mason
Info "Installing Mason (Python 3.11 + 400MB model on first onboard)..."
# uv python 3.11
try { uv python install 3.11 2>$null } catch {}

# Install from git (no clone needed)
try {
  uv pip install "git+https://github.com/$Repo.git" --python 3.11 2>$null
  if ($LASTEXITCODE -ne 0) { throw "pip failed" }
} catch {
  # Fallback: pip
  try { pip install "git+https://github.com/$Repo.git" } catch { Warn "pip install failed — ensure Git is installed and re-run" }
}

# 3. Onboard --yes (fetches 400MB Qwen2-0.5B, writes %LOCALAPPDATA%\mason\config.yaml)
Info "Onboarding (fetching 400MB 0.5B model — one-time)..."
try {
  mason onboard --yes
} catch {
  try { uv run mason onboard --yes } catch { Warn "onboard needs network — re-run: mason onboard --yes" }
}

Ok "Done — run: mason"
Write-Host "  mason              # chat"
Write-Host "  mason gateway      # Telegram/Discord"
Write-Host "  mason prompt-size  # verify ~17KB O(1) prompt"
