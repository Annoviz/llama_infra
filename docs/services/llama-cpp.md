# llama.cpp Stack

Three deployment modes for GGUF inference on Docker Compose: single-model native server, Python server with Jupyter, and multi-model router mode (drop-in Ollama/vLLM replacement).

## Architecture Overview

```
compose/llama/*.yml (split compose files)
├── 00-networks-and-volumes.yml     — Shared networks + volumes
├── 05-llamacpp-router-networks.yml — Router stack external network refs
├── 10-llamacpp-native.yml          — Single-model native server (:8080)
├── 15-llamacpp-router.yml          — Multi-model router mode (:8080 internal)
├── 20-llamacpp-py.yml              — Python server + Jupyter (:18000/:18888)
└── 25-llamacpp-router-gateway.yml  — LiteLLM gateway (:11434, Ollama API)
```

**Note**: The native/py stack and the router+gateway stack are **separate compose groups**. They can run simultaneously (different ports). The router+gateway group is mutually exclusive with Ollama and vLLM on port 11434.

## Images

| Image | Source | Usage |
|-------|--------|-------|
| `${LLAMA_CPP_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda13}` | ghcr.io | Native server + router (contains `llama-server` binary) |
| `${REGISTRY:-llamacpp-server-python}/llamacpp-server-py:${LLAMA_CPP_VERSION:-0.3.33}` | user registry | Python wrapper with Jupyter (:18000/:18888) |

Python build base: `${BASE_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda13}`

## Networks

| Network | Type | Purpose |
|---------|------|---------|
| `ollama-bridge` | External (`llama_infra_ollama-bridge`) | Shared across all stacks (Ollama, vLLM, router) for inter-stack comms |
| `ollama-local` | Bridge (internal) | Private network between router + gateway only |

The external `ollama-bridge` is created by the vLLM stack. Verify it exists before deploying:
```bash
docker network inspect llama_infra_ollama-bridge 2>&1 | head -3
```

## Mode 1: Native Server (Single Model)

A single `llama-server` process serving one GGUF model on port 8080. Simple, no proxy needed.

### Compose

- **File**: `compose/llama/10-llamacpp-native.yml`
- **Port**: `${LLAMA_CPP_PORT:-8080}:8080` (configurable via `.env`)
- **Service name**: `llamacpp-server`

### Configuration

Uses JSON model config files in `workspace/models/*.json`:

```bash
make up-llamacpp              # Start native server
make build-llamacpp           # Build image only
make logs-llamacpp            # Follow logs
```

The native server can run alongside router mode since they use different ports (8080 vs 11434).

## Mode 2: Python Server

A Python wrapper around llama.cpp with Jupyter notebook support. Useful for development and experimentation.

### Compose

- **File**: `compose/llama/20-llamacpp-py.yml`
- **Ports**: `${PY_SERVER_PORT:-18000}:18000` (API), `:18888` (Jupyter)
- **Service name**: `llamacpp-server-python`

### Build + Run

```bash
make build-llamacpp-py        # Build Python server image
make up-llamacpp-py           # Start Python server
make logs-llamacpp-py         # Follow logs
```

## Mode 3: Router Mode (Multi-Model)

The primary multi-model deployment. A single `llama-server` process serves multiple models on port 8080, with a separate LiteLLM gateway translating Ollama API format to OpenAI-compatible requests on port 11434.

### Architecture

```
Client (Claude Code CLI, etc.)  :11434
    │
    ▼
llamacpp-gateway (LiteLLM)      → /api/chat, /api/tags (Ollama API)
    │  config: workspace/llama/litellm_config.yaml
    ▼
llamacpp-router (:8080)         → /v1/chat/completions (OpenAI API)
    │  --models-preset: router-preset.ini
    │  --models-max: 2
    ▼
GGUF models (loaded on demand, LRU eviction)
```

### Compose Files

| File | Purpose | Service |
|------|---------|---------|
| `05-llamacpp-router-networks.yml` | Network definitions | — |
| `15-llamacpp-router.yml` | Router service + GPU reservation | `llamacpp-router` |
| `25-llamacpp-router-gateway.yml` | LiteLLM gateway (Ollama API) | `llamacpp-gateway` |

### Entrypoint Script

`scripts/entrypoint.llamacpp-router.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

PRESET="${LLAMA_ROUTER_PRESET:-/app/router-preset.ini}"
MODELS_MAX="${LLAMA_ROUTER_MODELS_MAX:-2}"
PORT=8080  # Fixed internal port; host mapping handled by Docker Compose

if [[ ! -f "${PRESET}" ]]; then
    echo "[llama-router] ERROR: Preset file not found at ${PRESET}" >&2
    exit 1
fi

echo "[llama-router] Preset: ${PRESET}, max models: ${MODELS_MAX}, port: PORT}"

exec /app/llama-server \
    --models-preset "${PRESET}" \
    --models-max "${MODELS_MAX}" \
    --port "${PORT}" \
    --host "0.0.0.0"
```

### Multi-Model Concurrent Loading

The router uses llama.cpp's native multi-model preset mode (`--model-preset`). Key behavior:

- **`--models-max N`** (default: 2) — Maximum number of models allowed in VRAM simultaneously. This is the critical parameter for concurrent loading.
- **No `--model-max-one` flag** — If this were passed, it would force single-model hot-swapping mode (evict current model when a different one is requested). Its absence allows concurrent residency.
- **LRU Eviction** — When VRAM is full and a new model is requested, the least-recently-used model is evicted to make room. This happens automatically based on actual GPU memory pressure, not just model count.
- **On-demand loading** — Models are loaded into GPU layers only when first requested via the API. They stay resident until eviction or shutdown.

### Preset Configuration

`workspace/models/router-preset.ini`:

```ini
[*]
# Global defaults applied to all model workers
ngl = 99              # All layers to GPU (0 = CPU, -1 = auto)
parallel = 2          # Concurrent sequences per loaded model (NOT multi-model)
mlock = true

[planner]
model = /models/Qwen3.6-35B-A3B-MTP/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
mmproj = /models/Qwen3.6-35B-A3B-MTP/mmproj-BF16.gguf
ctx-size = 131072
n-predict = 8192
batch-size = 4096
temp = 0.6
top-p = 0.90
repeat-penalty = 1.1
spec-type = draft-mtp
spec-draft-n-max = 2

[coder]
model = /models/Qwen3.6-27B-MTP/Qwen3.6-27B-UD-Q4_K_XL.gguf
mmproj = /models/Qwen3.6-27B-MTP/mmproj-BF16.gguf
ctx-size = 131072
batch-size = 2048
temp = 0.2
top-p = 0.80
repeat-penalty = 1.05
spec-type = draft-mtp
spec-draft-n-max = 2

[fast-coder]
model = /models/Qwen3.5-4B/Qwen3.5-4B-UD-Q4_K_XL.gguf
mmproj = /models/Qwen3.5-4B/mmproj-BF16.gguf
ctx-size = 131072
batch-size = 2048
temp = 0.2
top-p = 0.85
repeat-penalty = 1.05
```

**Key fields**:
- `ngl = 99` — All layers to GPU (effectively unlimited; GPU will load as many as fit)
- `parallel = 2` — Request-level parallelism for a single loaded model (concurrent sequences), NOT multi-model loading
- `spec-type = draft-mtp` + `spec-draft-n-max = 2` — MTP speculative decoding enabled for MTP models

### LiteLLM Gateway Config

`workspace/llama/litellm_config.yaml`:

```yaml
model_list:
  - model_name: planner
    litellm_params:
      model: openai/planner
      api_base: http://llamacpp-router:8080/v1
  - model_name: coder
    litellm_params:
      model: openai/coder
      api_base: http://llamacpp-router:8080/v1
  - model_name: fast-coder
    litellm_params:
      model: openai/fast-coder
      api_base: http://llamacpp-router:8080/v1

litellm_settings:
  drop_unsupported_params: true
```

Routes Ollama-format requests (`/api/chat`, `/api/tags`) to the correct backend worker by matching `model` parameter. Uses `openai/` prefix since llama.cpp router exposes OpenAI-compatible API, not `hosted_vllm/` (vLLM-only).

### VRAM Budget (RTX 6000 Ada, 48 GB)

With `--models-max=2`, up to two models can be resident simultaneously:

| Model | Quant | ~VRAM Weights | + KV Cache | Notes |
|-------|-------|---------------|------------|-------|
| Planner | Q4_K_XL + mmproj BF16 | ~18 GB | ~4 GB at 16k ctx | A3B-MTP variant, speculative decoding active |
| Coder | Q4_K_XL | ~16 GB | ~3 GB at 8k ctx | MTP variant, speculative decoding active |
| FastCoder | Q4_K_XL + mmproj BF16 | ~3 GB | ~1 GB at 4k ctx | Small; fits easily with either larger model |

**Recommended `--models-max=2`**. Planner + Coder together (~34 GB weights + ~7 GB KV cache) is tight but fits in 48 GB. FastCoder can comfortably coexist with either Planner or Coder.

If total footprint exceeds hardware, LRU eviction kicks in automatically — the least-recently-requested model gets unloaded to make room for the new one.

### Health Check + Startup Order

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 60s   # Router needs time to load first model

depends_on:
  llamacpp-router:
    condition: service_healthy
```

Gateway waits for router health check before starting. Router gets 60-second grace period for initial model loads.

### Make Targets

```bash
make up-llamacpp-router           # Start router + gateway stack
make down-llama                   # Stop entire llama.cpp stack (native + py)
make restart-llamacpp-router      # Restart router only (gateway auto-restarts)
make logs-llamacpp-router         # Follow router logs
make config-llamacpp-router       # Validate assembled compose config
```

The Makefile assembles the router+gateway via:
```makefile
COMPOSE_LLAMA_ROUTER = \
    -f compose/llama/05-llamacpp-router-networks.yml \
    -f compose/llama/15-llamacpp-router.yml \
    -f compose/llama/25-llamacpp-router-gateway.yml
```

### Switching Stacks

All three harnesses share port 11434 and are mutually exclusive:

```bash
# Ollama → Router
make down-main && make up-llamacpp-router

# vLLM → Router
make down-vllm && make up-llamacpp-router

# Router → Ollama (main)
make down-llamacpp-router && make up-main
```

### Prerequisites

- GGUF files must exist in `${MODELS}/` matching preset paths exactly
- mmproj files required for multimodal models (planner, fast-coder)
- llama.cpp image version must support `--models-preset` flag (full-cuda-b4738 tag includes it)
- External network `llama_infra_ollama-bridge` must exist (created by vLLM stack or manually)

### Debugging

```bash
# Check if router is healthy
curl -s http://localhost:8080/health

# See which model is currently loaded (from metrics endpoint)
curl -s http://localhost:8080/metrics | grep llama_model_load_all_secs

# Verify gateway routing
curl -s http://localhost:11434/api/tags

# Test Ollama-compatible chat via gateway
curl -s http://localhost:11434/api/chat -d '{
  "model": "planner",
  "messages": [{"role":"user","content":"hi"}],
  "stream": false
}' | python3 -c "import sys,json; print(json.load(sys.stdin)['message']['content'][:200])"

# Check VRAM usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLAMA_CPP_IMAGE` | `ghcr.io/ggml-org/llama.cpp:full-cuda-b4738` | Base image for all llama.cpp services |
| `LLAMA_ROUTER_PORT` | `8080` | Internal container port (not exposed to host directly) |
| `LLAMA_ROUTER_MODELS_MAX` | `2` | Max concurrent models in VRAM |
| `LLAMA_ROUTER_PRESET` | `/app/router-preset.ini` | Preset INI file path inside container |
| `VLLM_GATEWAY_PORT` | `11434` | Host port for gateway (Ollama API) — reused from vLLM stack |
| `LITELLM_VERSION` | `1.92.0` | LiteLLM Docker tag — shared with vLLM stack |

## Files

| File | Purpose |
|------|---------|
| `compose/llama/00-networks-and-volumes.yml` | Shared networks + volumes (native/py stack) |
| `compose/llama/05-llamacpp-router-networks.yml` | Router network definitions (external refs) |
| `compose/llama/10-llamacpp-native.yml` | Single-model native server |
| `compose/llama/15-llamacpp-router.yml` | Multi-model router service |
| `compose/llama/20-llamacpp-py.yml` | Python server + Jupyter |
| `compose/llama/25-llamacpp-router-gateway.yml` | LiteLLM gateway (Ollama API) |
| `scripts/entrypoint.llamacpp-router.sh` | Router entrypoint (sets up preset, max models, port) |
| `workspace/models/router-preset.ini` | Multi-model preset config (INI format) |
| `workspace/llama/litellm_config.yaml` | Gateway model routing config |

## Related Rules

- `.claude/rules/compose-validate-before-deploy.md` — validate assembled compose before deploy
- `.claude/rules/compose-external-network-check.md` — verify external networks exist
- `.claude/rules/registry-prefix-for-custom-images.md` — use `${REGISTRY:-...}` for custom images
- `.claude/rules/no-inline-comments-in-env-for-make.md` — inline comments break Make `-include .env`
