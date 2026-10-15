#!/usr/bin/env bash
# One-command setup: uv, Python dependencies, and a model to run against.
#
#   ./scripts/install.sh            # local model through Ollama (free, no key)
#   ./scripts/install.sh --hosted   # skip Ollama; use a hosted OpenAI-compatible API via .env
#
# Safe to re-run: every step checks what is already there.
set -euo pipefail

cd "$(dirname "$0")/.."

BASE_MODEL=qwen3:8b
MODEL=incident-qwen3

step() { printf '\n==> %s\n' "$*"; }
die() { printf '\nerror: %s\n' "$*" >&2; exit 1; }

hosted=false
case "${1:-}" in
  "") ;;
  --hosted) hosted=true ;;
  -h | --help) sed -n '2,7s/^# \{0,1\}//p' "$0"; exit 0 ;;
  *) die "unknown option: $1 (try --help)" ;;
esac

step "uv"
if ! command -v uv >/dev/null 2>&1; then
  command -v curl >/dev/null 2>&1 || die "curl is needed to install uv: https://docs.astral.sh/uv/"
  echo "Installing uv (user-level, no sudo)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${UV_INSTALL_DIR:-$HOME/.local/bin}:$PATH"
  command -v uv >/dev/null 2>&1 || die "uv installed but not on PATH; open a new shell and re-run"
fi
uv --version

step "Python dependencies"
uv sync  # uv fetches Python 3.12+ itself if the system has none

if $hosted; then
  step "Hosted model configuration"
  if [ -f .env ]; then
    echo ".env already exists; leaving it as is."
  else
    cp .env.example .env
    echo "Created .env. Uncomment the Groq or Gemini block and paste your API key."
  fi
else
  step "Ollama"
  if ! command -v ollama >/dev/null 2>&1; then
    case "$(uname -s)" in
      Darwin) hint="brew install ollama   (or download the app from https://ollama.com/download)" ;;
      Linux) hint="curl -fsSL https://ollama.com/install.sh | sh" ;;
      *) hint="see https://ollama.com/download" ;;
    esac
    die "Ollama is not installed. Install it with:
    $hint
then re-run this script. Or run './scripts/install.sh --hosted' to use a hosted API instead."
  fi

  if ! ollama list >/dev/null 2>&1; then
    echo "Starting the Ollama server in the background..."
    nohup ollama serve >/dev/null 2>&1 &
    for _ in $(seq 1 30); do
      ollama list >/dev/null 2>&1 && break
      sleep 1
    done
    ollama list >/dev/null 2>&1 || die "the Ollama server did not start; run 'ollama serve' and retry"
  fi

  echo "Pulling $BASE_MODEL (about 5 GB the first time)..."
  ollama pull "$BASE_MODEL"
  # Raises Ollama's 4k default context to 16k; agent conversations are truncated without it.
  ollama create "$MODEL" -f ollama/Modelfile
fi

step "Offline tests (no model or network)"
uv run pytest -q

step "Done"
if $hosted; then
  echo "After adding your key to .env:"
else
  echo "Try it:"
fi
cat <<'EOF'
  uv run investigate --scenario checkout_bad_config
  uv run evals
EOF
