#!/usr/bin/env bash
set -euo pipefail

PRESET="${LLAMA_ROUTER_PRESET:-/app/router-preset.ini}"
MODELS_MAX="${LLAMA_ROUTER_MODELS_MAX:-2}"
PORT=8080  # Fixed internal port; host mapping handled by Docker Compose

if [[ ! -f "${PRESET}" ]]; then
    echo "[llama-router] ERROR: Preset file not found at ${PRESET}" >&2
    exit 1
fi

echo "[llama-router] Preset: ${PRESET}, max models: ${MODELS_MAX}, port: ${PORT}"

exec /app/llama-server \
    --models-preset "${PRESET}" \
    --models-max "${MODELS_MAX}" \
    --port "${PORT}" \
    --host "0.0.0.0"
