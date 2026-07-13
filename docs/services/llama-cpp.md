# llama.cpp stack

## Project
- URL: `https://github.com/ggml-org/llama.cpp`
- Description: C/C++ inference stack for running GGUF models locally, with native and Python server options.

## Compose
- Files: `compose/llama/*.yml` (split compose files)
  - `00-networks-and-volumes.yml` — Shared networks
  - `10-llamacpp-native.yml` — Single-model native C++ server (:8080)
  - `20-llamacpp-py.yml` — Python server + Jupyter (:18000/:18888)
  - `15-llamacpp-router.yml` — Multi-model router mode (:11434, drop-in Ollama replacement)

## Images
- Native server: `${LLAMA_CPP_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda13}`
- Python server image: `${REGISTRY:-llamacpp-server-python}/llamacpp-server-py:${LLAMA_CPP_VERSION:-0.3.33}`
- Python build base image: `${BASE_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda13}`

## Make targets
### Native server (single model)
- `make up-llamacpp` — Start single-model native server (:8080)
- `make build-llamacpp` — Build the native llama.cpp server image
- `make logs-llamacpp` — Follow native server logs

### Python server
- `make build-llamacpp-py` — Build the python llama-cpp server image
- `make up-llamacpp-py` — Start the python llama-cpp server
- `make logs-llamacpp-py` — Follow Python server logs

### Router mode (multi-model, port 11434)
- `make up-llamacpp-router` — Start router mode (:11434, drop-in Ollama/vLLM replacement)
- `make down-llamacpp-router` — Stop router mode
- `make restart-llamacpp-router` — Restart router
- `make logs-llamacpp-router` — Follow router logs

### Shared
- `make down-llama` — Stop the entire llama.cpp stack (native + Python)

## Router Mode

Router mode runs a single `llama-server` process that serves multiple models on port 11434, acting as a drop-in replacement for Ollama and the vLLM gateway.

### How it works
- Uses llama.cpp's native multi-model preset (`--model-preset`)
- LRU VRAM eviction: loads models on demand, unloads least-recent when `--models-max` is exceeded
- No external proxy needed — unified `/v1/chat/completions` API
- **Mutually exclusive** with Ollama and vLLM gateway on port 11434

### Configuration
- Preset file: `workspace/models/router-preset.ini` (INI format, `[model]` sections)
- Model registry: `workspace/models/router-models.yaml`
- Max concurrent models: `LLAMA_ROUTER_MODELS_MAX=2` (default)
- Entrypoint: `scripts/entrypoint.llamacpp-router.sh`

### VRAM Budget (RTX 6000 Ada, 48 GB)
| Model | Quant | ~VRAM Weights | + KV Cache | Notes |
|-------|-------|---------------|------------|-------|
| Planner | Q4_K_XL + mmproj BF16 | ~18 GB | ~4 GB at 16k ctx | A3B-MTP variant |
| Coder | Q4_K_XL | ~16 GB | ~3 GB at 8k ctx | MTP variant |
| FastCoder | Q4_K_XL + mmproj BF16 | ~3 GB | ~1 GB at 4k ctx | Small; generous headroom |

Recommended `--models-max=2`. Planner + Coder together (~34 GB) is tight.

### Switching stacks
```bash
make down-main && make up-llamacpp-router   # Ollama → router
make down-vllm && make up-llamacpp-router    # vLLM → router
make down-llamacpp-router && make up-main    # Router → Ollama
```

### Prerequisites
- GGUF files must exist in `${MODELS}/` matching preset paths
- llama.cpp version must support `--model-preset` — verify before deploying:
- Update Modelfiles if switching model variants

## Notes
- This stack is separate from the main compose stack.
- GPU checks: `make gpu-host` and `make gpu-smoke-llamacpp`.
- The native server (:8080) can run alongside router mode (:11434).
