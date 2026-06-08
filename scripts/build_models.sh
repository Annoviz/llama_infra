#!/usr/bin/env bash
set -euo pipefail

# Resolves to the directory containing this script (repo root when placed there)
LLAMA_INFRA_DIR="${LLAMA_INFRA_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$LLAMA_INFRA_DIR"
echo "🔧 Building model aliases from $LLAMA_INFRA_DIR/workspace/models/ ..."

docker compose -f "$LLAMA_INFRA_DIR/docker-compose.yml" \
  exec -T ollama-server ollama create planner \
  -f "/app/workspace/models/Planner.Modelfile"

docker compose -f "$LLAMA_INFRA_DIR/docker-compose.yml" \
  exec -T ollama-server ollama create coder \
  -f "/app/workspace/models/Coder.Modelfile"

docker compose -f "$LLAMA_INFRA_DIR/docker-compose.yml" \
  exec -T ollama-server ollama create fast-codder \
  -f "/app/workspace/models/FastCodder.Modelfile"

echo ""
echo "✅ Done. Registered models:"
docker compose -f "$LLAMA_INFRA_DIR/docker-compose.yml" \
  exec -T ollama-server ollama list

