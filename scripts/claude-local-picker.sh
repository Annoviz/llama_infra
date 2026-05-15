#!/usr/bin/env bash
set -euo pipefail

OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
ANTHROPIC_BASE_URL_LOCAL="${ANTHROPIC_BASE_URL_LOCAL:-${OLLAMA_BASE_URL}/v1}"
ANTHROPIC_AUTH_TOKEN_LOCAL="${ANTHROPIC_AUTH_TOKEN_LOCAL:-ollama}"
CLAUDE_CONFIG_DIR_LOCAL="${CLAUDE_CONFIG_DIR_LOCAL:-$HOME/.claude-local}"

if ! command -v curl >/dev/null 2>&1; then
  echo "[error] curl is required." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[error] python3 is required." >&2
  exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "[error] claude CLI is not available in PATH." >&2
  exit 1
fi

if ! models_json="$(curl -fsSL "${OLLAMA_BASE_URL}/api/tags")"; then
  echo "[error] Unable to query Ollama models from ${OLLAMA_BASE_URL}." >&2
  exit 1
fi

mapfile -t models < <(
  printf '%s' "$models_json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for m in data.get("models", []):
    name = m.get("name")
    if name:
        print(name)
'
)

if [ "${#models[@]}" -eq 0 ]; then
  echo "[error] No local models found in Ollama." >&2
  exit 1
fi

echo "Available local Ollama models:"
for i in "${!models[@]}"; do
  printf "  %2d) %s\n" "$((i + 1))" "${models[$i]}"
done

read -r -p "Select model number (default 1): " choice
choice="${choice:-1}"

if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
  echo "[error] Invalid model number: $choice" >&2
  exit 1
fi

idx=$((choice - 1))
if [ "$idx" -lt 0 ] || [ "$idx" -ge "${#models[@]}" ]; then
  echo "[error] Selection out of range: $choice" >&2
  exit 1
fi

selected_model="${models[$idx]}"
echo "[info] Launching claude with ollama/${selected_model}"

export ANTHROPIC_BASE_URL="$ANTHROPIC_BASE_URL_LOCAL"
export ANTHROPIC_AUTH_TOKEN="$ANTHROPIC_AUTH_TOKEN_LOCAL"
export CLAUDE_CONFIG_DIR="$CLAUDE_CONFIG_DIR_LOCAL"

exec claude --model "ollama/${selected_model}"
