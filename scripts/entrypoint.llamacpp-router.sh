#!/usr/bin/env bash
set -euo pipefail

PRESET="${LLAMA_ROUTER_PRESET:-/app/router-preset.ini}"
MODELS_MAX="${LLAMA_ROUTER_MODELS_MAX:-2}"
PRISM_LM="${PRISM_LM:-0}"  # Default to 0 if not set
LLAMA_SERVER_BIN="/app/llama-server"
PORT=8080  # Fixed internal port; host mapping handled by Docker Compose

if [[ ! -f "${PRESET}" ]]; then
    echo "[llama-router] ERROR: Preset file not found at ${PRESET}" >&2
    exit 1
fi

echo "[llama-router] Preset: ${PRESET}, max models: ${MODELS_MAX}, port: ${PORT}, PRISM_LM: ${PRISM_LM}"
if [[ "${PRISM_LM}" -eq 1 ]]; then
    echo "[llama-router] PrismLM support is enabled."
    LLAMA_SERVER_BIN="/app/prism-ml/llama-server"
else
    echo "[llama-router] PrismLM support is disabled."
fi

exec "${LLAMA_SERVER_BIN}" \
    --models-preset "${PRESET}" \
    --models-max "${MODELS_MAX}" \
    --port "${PORT}" \
    --host "0.0.0.0"
