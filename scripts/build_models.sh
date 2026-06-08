#!/usr/bin/env bash
set -euo pipefail

# Resolves to the directory containing this script (repo root when placed there)
LLAMA_INFRA_DIR="${LLAMA_INFRA_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$LLAMA_INFRA_DIR"
COMPOSE=(
  docker compose --project-directory "$LLAMA_INFRA_DIR"
  -f "$LLAMA_INFRA_DIR/compose/main/00-networks-and-volumes.yml"
  -f "$LLAMA_INFRA_DIR/compose/main/10-ollama.yml"
)

echo "🔧 Building model aliases from $LLAMA_INFRA_DIR/workspace/models/ ..."

"${COMPOSE[@]}" \
  exec -T ollama-server ollama create planner \
  -f "/app/workspace/models/Planner.Modelfile"

"${COMPOSE[@]}" \
  exec -T ollama-server ollama create coder \
  -f "/app/workspace/models/Coder.Modelfile"

"${COMPOSE[@]}" \
  exec -T ollama-server ollama create fast-codder \
  -f "/app/workspace/models/FastCodder.Modelfile"

echo ""
echo "✅ Done. Registered models:"
"${COMPOSE[@]}" \
  exec -T ollama-server ollama list

