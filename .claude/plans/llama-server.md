# llama.cpp Router Mode — Implementation & Changes

**Status**: Implemented (2026-07-16). Router starts, all 3 models registered, vision test passes.

## Changelog (2026-07-16)

### Bug Fixes

#### Entrypoint — `scripts/entrypoint.llamacpp-router.sh`
- **Line 15**: `llama-server` → `/app/llama-server` (binary at `/app/`, not in container PATH)
- **Line 16**: `--model-preset` → `--models-preset` (CLI flag is plural per `--help`)

#### Preset INI — `workspace/models/router-preset.ini`
Preset parser uses **CLI flag names** (hyphenated), not env var names (underscored):
- `[*]`: `n_parallel` → `parallel`
- All models: `n_batch` → `batch-size`
- All models: `top_p` → `top-p`
- planner: `n_predict` → `n-predict`

#### Compose — `compose/llama/15-llamacpp-router.yml`
- Removed `networks:` block entirely (`llamacpp-bridge` unused, `ollama-bridge` was fragile cross-stack dependency)

#### Compose — `compose/llama/10-llamacpp-native.yml`
- Port: `8080:8080` → `${LLAMA_CPP_PORT:-8080}:8080` (env override)
- Comment: fixed misleading `# default entrypoint: /app/tools.sh`

#### Makefile
- Removed `build-llamacpp` target (no Dockerfile for native image — it's pre-built)
- Added `LLAMA_CPP_PORT`, `LLAMA_ROUTER_PORT`, `LLAMA_ROUTER_MODELS_MAX` to env docs
- Fixed vision-test: shell-side defaults (`$${VAR:-default}`) instead of Make `$(VAR:-default)` which breaks when Bash passes empty env vars
- Added `--api-format` and `API_FORMAT` variable to vision-test

#### Vision test — `scripts/vision_test.py`
- Added OpenAI API support via `vision_generate_openai()` using `/v1/chat/completions`
- New `--api-format` CLI flag: `ollama` (default) or `openai`
- Updated dispatcher and main to pass `mime_type` and `api_format`

#### `.env`
- Added `LLAMA_CPP_PORT=8080`

### Verification
```bash
make up-llamacpp-router
# Container: healthy, 3 models registered (planner, coder, fast-coder)
# API: curl http://localhost:21434/v1/models → 200 OK

make vision-test MODEL=fast-coder IMAGE=workspace/data/person.png \
  OLLAMA_BASE_URL=http://localhost:21434 API_FORMAT=openai
# Result: 272 tokens, 67 TPS, correct image description
```

## Goal

Replace the current single-model `llama-server` with a **multi-model router** that serves all three models (planner, coder, fastcoder) on port 11434 — a drop-in replacement for Ollama and vLLM gateway. Uses llama.cpp's native router mode (`--models-preset`), so no external proxy is needed.

## Why Router Mode?

- Eliminates LiteLLM dependency for llama.cpp stack
- Single process, single port (11434), unified `/v1/chat/completions` API — drop-in for Ollama/vLLM
- Dynamic LRU VRAM eviction: loads models on demand, unloads least-recent when `--models-max` is exceeded
- Native `mmproj` support via preset file — no directory auto-discovery for multimodal

## Architecture

```
llama-server (Router Mode, :11434)
├── [planner]     → Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL + mmproj   (~18 GB VRAM)
├── [coder]       → Qwen3.6-27B-MTP-UD-Q4_K_XL                (~16 GB VRAM)
└── [fast-coder]  → Qwen3.5-4B-UD-Q4_K_XL + mmproj             (~3 GB VRAM)
```

Single container, single GPU. Models are loaded/unloaded dynamically based on requests and `--models-max`. On a 48 GB RTX 6000 Ada:
- Planner alone fits comfortably (~18 GB quantized)
- Planner + FastCoder fit simultaneously (~21 GB)
- All three together would need ~37 GB — tight but possible with Q4_K_XL

## Contract

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `compose/llama/00-networks-and-volumes.yml` | Update | Add `llamacpp-bridge` network + external `ollama-bridge` (same pattern as vLLM) |
| `compose/llama/15-llamacpp-router.yml` | Create | Router mode service — single container, preset file |
| `workspace/models/router-preset.ini` | Create | `[<slug>]` sections mapping model + mmproj + per-model overrides |
| `scripts/entrypoint.llamacpp-router.sh` | Create | Entrypoint: validates preset, exec llama-server |
| `workspace/models/router-models.yaml` | Create | Model registry for router (parallel to vLLM registry) |
| `Makefile` | Update | Add `up-llamacpp-router`, `down-llamacpp-router`, `logs-llamacpp-router`, `restart-llamacpp-router` |
| `.env` | Update | Add env vars for router mode |
| `docs/services/llama-cpp.md` | Update | Document router mode, preset file, VRAM constraints |

### Preset File (`workspace/models/router-preset.ini`)

Global settings in `[*]`, per-model overrides in `[<slug>]` sections. Keys map to CLI flags (kebab-case → INI key).

```ini
[*]
# Global defaults applied to all model workers
ngl = 99
n_parallel = 2
flash-attn = true
mlock = true
offload-kqv = true
cache-type-k = q8_0
cache-type-v = q8_0

[planner]
model = /models/Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL.gguf
mmproj = /models/mmproj-Qwen3.6-35B-BF16.gguf
ctx-size = 131072
n_predict = 8192
n_batch = 4096
n_kv_bins = 256
temp = 0.6
top_p = 0.90
repeat-penalty = 1.1
spec-type = draft-mtp
spec-draft-n-max = 2

[coder]
model = /models/Qwen3.6-27B-MTP-UD-Q4_K_XL.gguf
ctx-size = 8192
n_batch = 2048
n_kv_bins = 256
temp = 0.1
top_p = 0.80
repeat-penalty = 1.05
spec-type = draft-mtp
spec-draft-n-max = 2

[fast-coder]
model = /models/Qwen3.5-4B-UD-Q4_K_XL.gguf
mmproj = /models/mmproj-Qwen3.5-4B-BF16.gguf
ctx-size = 131072
n_batch = 2048
n_kv_bins = 128
temp = 0.2
top_p = 0.85
repeat-penalty = 1.05
```

**Per-model rationale (from Ollama Modelfiles):**

| Setting | Planner | Coder | FastCoder | Source |
|---------|---------|-------|-----------|--------|
| `ctx-size` | 131072 | 8192 | 131072 | Planner/FastCoder need huge context for Claude Code system prompts + files; coder uses vLLM max-len (8k) |
| `n_predict` | 8192 | — | — | From Planner Modelfile — max tokens to generate |
| `temp` | 0.6 | 0.1 | 0.2 | Planner: higher for creative reasoning; Coder/FastCoder: low for deterministic code |
| `top_p` | 0.90 | 0.80 | 0.85 | From Modelfiles — nucleus sampling thresholds |
| `repeat-penalty` | 1.1 | 1.05 | 1.05 | Planner: stronger penalty (longer gens loop more); Coder/FastCoder: mild per Qwen3 alignment |
| `spec-type` | draft-mtp | draft-mtp | — | Both A3B-MTP and MTP variants have auxiliary prediction heads; FastCoder does not |
| `n_batch` | 4096 | 2048 | 2048 | Processing batch size; planner gets more for longer prompts |
| `n_kv_bins` | 256 | 256 | 128 | NVMT attention bins — limits peak KV memory (equivalent to vLLM's chunked-prefill concept) |

**Global optimization flags:**

| Setting | Value | Why |
|---------|-------|-----|
| `flash-attn` | true | Flash attention for RTX 6000 Ada (same as vLLM's flashinfer, but llama.cpp uses flash-attn) |
| `mlock` | true | Prevent model from being swapped to disk |
| `offload-kqv` | true | Offload K/Q/V tensors to GPU |
| `cache-type-k/v` | q8_0 | FP8-equivalent quantized KV cache (halves precision vs default F16 — same as vLLM's `--kv-cache-dtype fp8`) |

### Router Service (`compose/llama/15-llamacpp-router.yml`)

Follows vLLM structure conventions: numbered prefix, split compose file, env-driven config. Custom entrypoint passes args directly to `llama-server` — no reliance on the official image's `tools.sh`. Internal port is fixed at 8080; host mapping handles the drop-in replacement on 11434.

```yaml
services:
  llamacpp-router:
    image: ${IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda-b5350}
    shm_size: '8gb'
    container_name: llamacpp-router
    entrypoint: ["/app/scripts/entrypoint.llamacpp-router.sh"]
    ulimits:
      memlock: -1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["${GPU_ID:-0}"]
              capabilities: [gpu]
    ports:
      - "${LLAMA_ROUTER_PORT:-11434}:8080"  # Host port → container port (fixed at 8080)
    volumes:
      - ${MODELS:-./models}:/models
      - ./workspace/models/router-preset.ini:/app/router-preset.ini:ro
      - ./scripts/entrypoint.llamacpp-router.sh:/app/scripts/entrypoint.llamacpp-router.sh:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/v1/models"]  # Internal port is always 8080
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    networks:
      - llamacpp-bridge
      - ollama-bridge
    restart: unless-stopped

networks:
  llamacpp-bridge:
    driver: bridge
  ollama-bridge:
    external: true
    name: llama_infra_ollama-bridge
```

Note: No `LLAMA_ARG_*` env vars — the custom entrypoint reads the preset file path and passes args directly to `llama-server`. The official image's `tools.sh` entrypoint (which translates `LLAMA_ARG_*` env vars to CLI flags) is bypassed.

### Entrypoint (`scripts/entrypoint.llamacpp-router.sh`)

Internal port is fixed at 8080 (llama-server default). Host-side mapping to 11434 is handled by Docker Compose `ports` — the container doesn't know about it.

```bash
#!/usr/bin/env bash
set -euo pipefail

PRESET="/app/router-preset.ini"
MODELS_MAX="${LLAMA_ROUTER_MODELS_MAX:-2}"
PORT=8080  # Fixed internal port; host mapping handled by Docker Compose

if [[ ! -f "${PRESET}" ]]; then
    echo "[llama-router] ERROR: Preset file not found at ${PRESET}" >&2
    exit 1
fi

echo "[llama-router] Preset: ${PRESET}, max models: ${MODELS_MAX}, port: ${PORT}"

exec llama-server \
    --models-preset "${PRESET}" \
    --models-max "${MODELS_MAX}" \
    --port "${PORT}" \
    --host "0.0.0.0"
```

### Env Vars (`.env`)

```bash
LLAMA_ROUTER_PORT=11434  # Same port as Ollama and vLLM gateway — drop-in replacement
LLAMA_ROUTER_MODELS_MAX=2
IMAGE=ghcr.io/ggml-org/llama.cpp:full-cuda-b5350
```

### Makefile Targets

Separate compose variable — mutually exclusive with Ollama and vLLM gateway on port 11434:

```makefile
COMPOSE_LLAMA_ROUTER := docker compose \
    -f compose/llama/15-llamacpp-router.yml

up-llamacpp-router: ## Start llama.cpp router mode
	$(COMPOSE_LLAMA_ROUTER) up -d

down-llamacpp-router: ## Stop llama.cpp router mode
	$(COMPOSE_LLAMA_ROUTER) down

logs-llamacpp-router: ## Router logs
	$(COMPOSE_LLAMA_ROUTER) logs -f llamacpp-router

restart-llamacpp-router: ## Restart router
	$(COMPOSE_LLAMA_ROUTER) restart llamacpp-router
```

### Model Registry (`workspace/models/router-models.yaml`)

Mirrors `vllm-models.yaml` structure for consistency. Uses `gguf_path` instead of `hf_repo` (models are local GGUF files, not HF downloads).

```yaml
router_mode: true
models_max: 2
optimization:
  flash_attn: true
  mlock: true
  offload_kqv: true
  cache_type_kv: q8_0  # FP8-equivalent quantized KV cache (like vLLM --kv-cache-dtype fp8)

models:
  - id: planner
    served_name: planner
    gguf_path: /models/Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL.gguf
    mmproj: /models/mmproj-Qwen3.6-35B-BF16.gguf
    format: q4_k_xl
    ctx_size: 131072
    n_predict: 8192
    n_batch: 4096
    temp: 0.6
    top_p: 0.90
    multimodal: true
    spec_type: draft-mtp
    notes: "A3B-MTP — has auxiliary prediction heads; higher temp for creative reasoning"

  - id: coder
    served_name: coder
    gguf_path: /models/Qwen3.6-27B-MTP-UD-Q4_K_XL.gguf
    format: q4_k_xl
    ctx_size: 8192
    n_batch: 2048
    temp: 0.1
    top_p: 0.80
    multimodal: false
    spec_type: draft-mtp
    notes: "MTP variant — has auxiliary prediction heads"

  - id: fast-coder
    served_name: fast-coder
    gguf_path: /models/Qwen3.5-4B-UD-Q4_K_XL.gguf
    mmproj: /models/mmproj-Qwen3.5-4B-BF16.gguf
    format: q4_k_xl
    ctx_size: 131072
    n_batch: 2048
    temp: 0.2
    top_p: 0.85
    multimodal: true
```

## Optimization Comparison: vLLM vs llama.cpp Router

| Concept | vLLM Flag | llama.cpp Preset Key | Notes |
|---------|-----------|---------------------|-------|
| Flash attention | `--attention-backend flashinfer` | `flash-attn = true` | Ada arch supported in both; different kernel libraries |
| KV cache quantization | `--kv-cache-dtype fp8` | `cache-type-k/v = q8_0` | Same concept — q8_0 ≈ FP8 precision, halves memory vs F16 |
| Chunked prefill / peak memory cap | `--enable-chunked-prefill --max-num-seqs 256` | `n_kv_bins = 256` | n_kv_bins limits NVMT attention bins, capping peak KV memory |
| GPU memory fraction | `--gpu-memory-utilization 0.92` | N/A (uses all available) | llama.cpp offloads all layers (`ngl=99`) and uses remaining VRAM for cache |
| Multimodal encoder | `--mm-encoder-tp-mode data` | `mmproj = ...` in section | Preset ties mmproj to model; no separate tensor parallel flag needed |

## Key Differences from vLLM Stack

| Aspect | vLLM Stack | llama.cpp Router |
|--------|-----------|------------------|
| Containers | 4 (3 engines + gateway) | 1 (single process, workers spawned internally) |
| Routing | LiteLLM proxy | Native `llama-server` router mode |
| VRAM model | All loaded simultaneously | LRU eviction, dynamic load/unload |
| Concurrent models | All always warm | Configured via `--models-max` |
| Multimodal | `--mmproj` flag per engine | `[section] mmproj = ...` in preset |
| Speculation | N/A (vLLM) | `spec-type = draft-mtp` in preset |

## VRAM Budget (RTX 6000 Ada, 48 GB)

| Model | Quant | ~VRAM Weights | + KV Cache (q8_0) | Notes |
|-------|-------|---------------|-------------------|-------|
| Planner | Q4_K_XL + mmproj BF16 | ~18 GB | ~4 GB at 16k ctx | mmproj is BF16 (~2 GB resident) |
| Coder | Q4_K_XL | ~16 GB | ~3 GB at 8k ctx | No multimodal overhead |
| FastCoder | Q4_K_XL + mmproj F16 | ~3 GB | ~1 GB at 4k ctx | Small; generous cache headroom |

Recommended `--models-max=2`. Pairings:
- **Planner + FastCoder** (~21 GB weights) — ideal, leaves 27 GB for KV caches
- **Coder + FastCoder** (~19 GB weights) — comfortable fit
- **Planner + Coder** (~34 GB weights) — tight; limited KV cache headroom

## Migration Notes

- Current `compose/llama/10-llamacpp-native.yml` (single model, port 8080) stays as fallback — different port, can coexist
- Router mode is **mutually exclusive** with Ollama and vLLM gateway on port 11434. Stop one before starting another:
  ```bash
  make down-main && make up-llamacpp-router   # Switch from Ollama to router
  make down-vllm && make up-llamacpp-router    # Switch from vLLM to router
  make down-llamacpp-router && make up-main    # Back to Ollama
  ```
- Python server (`20-llamacpp-py.yml`, port 18000/18888) is unaffected — can run alongside router
- Existing `entrypoint.llamacpp.sh` targets the Python server, not affected

## Pre-requisites / Open Questions

1. **GGUF files**: Models need to be downloaded as GGUF to `${MODELS}/`. Preset file paths must match actual filenames on disk.
2. **llama.cpp version**: Router mode requires `b5300+`. Current image is `full-cuda-b5350` — verify with:
   ```bash
   docker run --rm ghcr.io/ggml-org/llama.cpp:full-cuda-b5350 llama-server --help 2>&1 | grep -E 'models-preset|models-max'
   ```
3. **Preset key names**: Verify that `flash-attn`, `cache-type-k`, `n_kv_bins` are valid INI keys in the preset format by testing with a minimal preset before full deployment.
