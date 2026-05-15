# AGENTS.md - AI Agent Guide for llama_infra

This project is a **Docker-based LLM infrastructure** supporting multiple inference engines (Ollama, llama.cpp) and web interfaces (AnythingLLM, Open WebUI). Here's what AI agents need to know.

## Architecture Overview

**Two independent Docker stacks:**

1. **Main Stack** (`docker-compose.yml`): Ollama server + AnythingLLM + Open WebUI
   - Ollama: LLM inference on port 11434
   - AnythingLLM: Web UI on port 3001 (dependency: Ollama)
   - Open WebUI: Web UI on port 3002 (dependency: Ollama)

2. **llama.cpp Stack** (`docker-compose.llama.cpp.yml`): C++ and Python inference servers
   - Native C++ server on port 8080
   - Python server on port 18000 (FastAPI) + 18888 (Jupyter)

**Critical architectural decision**: Two separate compose files allow independent deployment of different LLM inference implementations. Services are NOT cross-stack compatible.

## Key Workflows & Commands

**Always use `make` commands, not docker commands directly:**

```bash
# Main stack operations (Ollama + web UIs)
make up-main          # Start all three services
make down-main        # Stop main stack
make ps-main          # Check status
make logs-ollama      # View Ollama logs (use for debugging)

# llama.cpp stack operations
make up-llamacpp      # Start C++ server
make up-llamacpp-py   # Start Python server
make down-llama       # Stop llama.cpp stack

# Configuration & diagnostics
make config-all       # Validate both compose files
make pull-all         # Pre-pull all images
make gpu-host         # Check NVIDIA GPU availability

# Version maintenance
make updates-check    # Check Docker tags + requirements-dev.txt package updates
make updates-suggest  # Write .update-manager-proposal.json with suggestions
make updates-apply    # Interactive yes/no prompt before writing changes
```

**Makefile pattern**: All targets expand to `docker compose -f <file> <command>`. Inspect the Makefile (lines 4-5) to understand composition file selection.

## Configuration & Model Management

**Model loading mechanism** (defined in `entrypoint.sh` and `docker-compose.llama.cpp.yml`):

1. Environment variable `LLM_CONFIG` specifies config file name (default: `config.json`)
2. Config file path resolved to `/app/workspace/configs/${LLM_CONFIG}`
3. Models specified in JSON config with full paths `/models/<model-name>/<file>`
4. Multiple models per config file supported (array in JSON)

**Config file structure** (`workspace/configs/*.json`):
```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "models": [{
    "model": "/models/path/model.gguf",
    "clip_model_path": "/models/path/mmproj.gguf",  // For multimodal models
    "model_alias": "user-friendly-name",
    "chat_format": "qwen" | "llava-1-5",            // Model-specific format
    "n_gpu_layers": -1,                             // -1 = all layers on GPU
    "n_threads": 12,
    "n_batch": 512,
    "n_ctx": 4096,
    "verbose": true
  }]
}
```

**To add new model configurations**: Copy existing config, update paths and model_alias, mount at runtime.

## Environment & Dependency Management

**Requirements files and roles:**

| File | Purpose | When Used |
|------|---------|-----------|
| `requirements-client.txt` | Minimal: openai, ollama, jupyter | Local development, client scripts |
| `requirements-dev.txt` | Main editable dependency set for Python server | Docker build and day-to-day updates |
| `workspace/requirements.txt` | Frozen environment snapshot | Jupyter notebooks / reproducible final state |

**Version pinning strategy**: Base images have pinned tags (`ollama/ollama:0.18.3`, `ghcr.io/ggml-org/llama.cpp:full-cuda-b5350`). Use `Makefile` overrides to test new versions:
```bash
OLLAMA_VERSION=0.19.0 make config-main  # View changes without deploying
```

**Update manager behavior** (`tools/update_manager.py`):
- Updates only managed defaults in compose/dockerfile + `requirements-dev.txt`
- Treats `workspace/requirements.txt` as frozen snapshot (report-only / never edited)
- `make updates-apply` always asks for interactive confirmation (`y`/`yes`) unless explicitly bypassed

## GPU Configuration & NVIDIA Docker

**GPU binding happens at container level** (`docker-compose.yml` lines 10-13):
```yaml
devices:
  - driver: nvidia
    device_ids: ["${GPU_ID:-0}"]      # Override with GPU_ID=1
    capabilities: [gpu]
```

**Verify GPU access:**
```bash
make gpu-host                    # nvidia-smi on host
make gpu-smoke-llamacpp          # Test CUDA in container
```

**Common issue**: Container sees GPU but CUDA unavailable → Check `LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH` in Dockerfile (lines 6-9).

## Volumes & Data Persistence

**Standard mounting pattern** (all compose files):
- `/models`: Host models → Container `/models` (read-only workload)
- `./workspace`: Project workspace → Container `/app/workspace`
- `.jupyter`: Jupyter config → Container `/root/.jupyter`
- `data/`: Persistent UI state → Container data paths

**Override paths via environment** (`.env` file):
```dotenv
MODELS=/custom/path/to/models        # Default: ./models
DATA_DIR=/custom/path/to/data        # Default: ./data
```

**Critical**: Never `rm -rf ./models` after deployment; models are large and downloaded on-demand.

## Python Server Integration (llama-cpp-python)

**Server runs dual processes** (`entrypoint.sh`):
1. Jupyter Lab on port 8888 (background: `jupyter-lab --no-browser --allow-root`)
2. FastAPI llama.cpp server on port 8000 (foreground)

**Server start command** (line 7):
```bash
python3 -m llama_cpp.server --config_file /app/workspace/configs/${LLM_CONFIG}
```

**Exposed ports**:
- `18000:8000` - FastAPI health/inference (maps to container 8000)
- `18888:8888` - Jupyter notebooks

**Python client example** (use `requirements-client.txt` + Jupyter):
```python
from openai import OpenAI
client = OpenAI(api_key="not-needed", base_url="http://localhost:18000/v1")
response = client.chat.completions.create(
    model="qwen2.5-vl",  # matches config "model_alias"
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Build & Deployment Patterns

**Building custom Python server** (uses build args for flexibility):
```bash
LLAMA_CPP_VERSION=0.3.19 \
REQUIREMENTS_FILE=requirements-dev.txt \
make build-llamacpp-py
```

**Dockerfile patterns** (`Dockerfile.llamacpp-server-python`):
- Line 1: ARG-first pattern allows base image override
- Line 11: nvcc verification ensures CUDA compilation
- Line 24: CMAKE_CUDA_ARCHITECTURES for multi-GPU compatibility (70, 75, 80, 86)

**Registry override** (`.env` REGISTRY var):
- Default: local build (`llamacpp-server-python/llamacpp-server-py:0.3.19`)
- Custom: `dk-server:5000/llamacpp-server-py:0.3.19` (push/pull model)

## Service Dependencies & Health Checks

**Declare dependency order** (compose `depends_on` at top-level service):
- AnythingLLM requires Ollama healthy
- Open WebUI requires Ollama healthy
- Python server independent; Native C++ server independent

**No explicit health checks in compose files** → Watch logs for startup:
```bash
make logs-ollama 2>&1 | grep -i "listening\|ready\|error"
```

**Port conflicts**: Ollama hardcoded to 11434. If port taken, rebuild image won't help; check host processes:
```bash
sudo lsof -i :11434
```

## Debugging & Common Issues

**Service won't start?**
1. Check compose file syntax: `make config-all`
2. View logs immediately: `make logs-<service-name>`
3. Verify volumes mounted: `docker inspect llama_infra-<service>-1 | grep Mounts`

**GPU not detected in container?**
```bash
# From host
nvidia-smi  # See GPU

# From container
docker exec <container> nvidia-smi  # Should match host

# If container nvidia-smi fails: missing driver or runtime
docker run --rm --gpus all nvidia/cuda:12.4.1-runtime nvidia-smi
```

**Model load failures** (check config paths):
- Error: `model file not found` → `/models/path` doesn't exist inside container
- Verify host mount: `docker inspect <container> | grep -A5 Mounts`
- Note: MODELS in `.env` uses full host path; compose file volume defaults to `./models`

## Project Conventions

1. **Config-first approach**: All model/host settings in JSON configs, not hardcoded
2. **Dual-stack design**: Supports experimenting with different inference engines simultaneously
3. **Environment layering**: .env → docker-compose.yml env → container env (each overrides previous)
4. **Jupyter-integrated**: llama.cpp Python server doubles as interactive dev environment
5. **GPU-optional**: Services degrade gracefully if GPU unavailable (CPU-only fallback not tested)

## Adding New Features

**Add new service to main stack:**
1. Add service block to `docker-compose.yml`
2. Set `depends_on: [ollama-server]` if needs Ollama
3. Add Makefile targets: `up-<service>`, `logs-<service>`, `down-main` already stops it
4. Test: `make config-main` then `make up-main`

**Add new llama.cpp model config:**
1. Download GGUF + mmproj files to `./models/<model-name>/`
2. Copy `workspace/configs/config.json` to `workspace/configs/<model-name>-config.json`
3. Update paths and `model_alias`
4. Deploy: `LLM_CONFIG=<model-name>-config.json docker compose -f docker-compose.llama.cpp.yml up -d llamacpp-server-py`

**Extend Python server dependencies:**
- Edit `requirements-dev.txt`
- Rebuild: `make build-llamacpp-py`
- Restart: `make restart-llamacpp-py`


