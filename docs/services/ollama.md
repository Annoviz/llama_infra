# Ollama Stack

Drop-in LLM runtime on port 11434: model manager + inference server. The default harness for Claude Code CLI integration before the vLLM and llama.cpp router stacks were added.

## Architecture

```
ollama-server (:11434)
├── Ollama Go daemon (PID 1 via image entrypoint)
├── CGO layer → C++ inference engine (custom fork of llama.cpp)
└── Model cache: ${MODELS:-./models} on host, /models in container
```

## Compose

- **File**: `compose/main/10-ollama.yml`
- **Service name**: `ollama-server`
- **Image**: `ollama/ollama:${OLLAMA_VERSION:-0.31.2}`
- **Port**: `11434:11434` (fixed, not configurable via `.env`)
- **Networks**: `ollama-bridge` (shared with vLLM gateway and llama.cpp router)

### GPU Configuration

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          device_ids: ["${GPU_ID:-0}"]
          capabilities: [gpu]
```

Uses `GPU_ID` from `.env` (default: 0). Container gets exclusive access to the specified GPU via NVIDIA runtime.

### Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `OLLAMA_MODELS` | `/models` | Path inside container for model storage |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | KV cache quantization (`f16`, `q8_0`, `q4_0`) |
| `OLLAMA_FLASH_ATTENTION` | `1` | Enable flash attention kernel |
| `OLLAMA_MAX_LOADED_MODELS` | `2` | Max models resident in VRAM simultaneously |
| `OLLAMA_NUM_PARALLEL` | `4` | Concurrent request slots per model |
| `OLLAMA_KEEP_ALIVE` | `30m` | Models stay loaded for 30 min after last request before eviction |
| `OLLAMA_CONTEXT_LENGTH` | `131072` | Max context window (token count) |
| `OLLAMA_DRAFT_MTP` | `1` | Enable MTP speculative decoding for MTP models |
| `OLLAMA_CUDA_DRIVERS` | `1` | Use CUDA drivers |
| `OLLAMA_NUM_PREDICT` | `8192` | Default max tokens per response |
| `OLLAMA_MAX_QUEUE` | `64` | Max queued requests across all models |

### Storage

- **Models**: `${MODELS:-./models}:/models` — GGUF files synced via Makefile target, Ollama manages its own manifest format (`manifests/`, `blobs/`)
- **Workspace**: `./workspace:/app/workspace` — Modelfiles and config scripts
- **Entrypoint**: `scripts/entrypoint.ollama.sh` (mounted read-only; currently commented out in compose)

### Model Storage Format

Ollama does NOT use GGUF files directly from disk. It stores models in its own blob format:

```bash
docker exec ollama-server ls /models/blobs/   # Internal model blobs
docker exec ollama-server ollama list          # List loaded models with sizes
```

To rebuild after Modelfile edits, run:
```bash
docker exec ollama-server ollama create <name> -f /workspace/models/<NAME>.Modelfile
```

See `.claude/rules/rebuild-model-after-modelfile-edit.md` for the full workflow.

## Models

Models are defined by Modelfiles in `workspace/models/`:

| Model | Modelfile | Description |
|-------|-----------|-------------|
| planner | `planner.Modelfile` | Qwen3.6-27B-MTP — reasoning, code generation |
| coder | `coder.Modelfile` | Code-focused model (variant) |

### Model Aliases in Claude Code

Set via `/model <name>` command or in Claude Code settings:
```
/model planner    # → Qwen3.6-27B-MTP UD-Q4_K_XL
/model fast-coder # → Qwen3.5-4B (session default)
```

## VRAM Budget (RTX 6000 Ada, 48 GB)

Ollama can hold up to `OLLAMA_MAX_LOADED_MODELS=2` models simultaneously:

| Model | Quant | ~VRAM Weights | + KV Cache | Notes |
|-------|-------|---------------|------------|-------|
| Planner (Qwen3.6-27B-MTP) | Q4_K_XL | ~16 GB | ~4 GB at 16k ctx | MTP speculative decoding active |
| FastCoder (Qwen3.5-4B) | Q4_K_XL | ~3 GB | ~1 GB at 4k ctx | Small; fits easily with planner |

`OLLAMA_KEEP_ALIVE=30m` means both models stay in VRAM for 30 minutes after their last request — no automatic eviction on idle.

## Make Targets

```bash
make up-ollama              # Start Ollama server
make down-main              # Stop entire main stack (Ollama + AnythingLLM + Open WebUI)
make logs-ollama            # Follow Ollama logs
make restart-ollama         # Restart Ollama container
make models-sync            # Sync model files from host to container workspace
```

## Mutual Exclusivity

The vLLM stack and llama.cpp router are **mutually exclusive** on port 11434. The main stack (including Ollama) shares this port, so:

```bash
make down-vllm && make up-main    # Stop vLLM, start Ollama
make down-llamacpp-router && make up-main   # Stop router, start Ollama
make down-main && make up-vllm    # Stop Ollama, start vLLM
```

## Verification

Check what's actually loaded:

```bash
# VRAM usage (quick sanity check)
nvidia-smi | grep MiB

# List all models with sizes
curl -s http://localhost:11434/api/tags \
  | python3 -c "import sys,json; [print(f'{m[\"name\"]:50s} {m.get(\"size\",\"\"):>12}') for m in json.load(sys.stdin)['models']]"

# Check specific model details
curl -s http://localhost:11434/api/show -d '{"name":"planner"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('model','N/A'))"
```

See `.claude/rules/verify-loaded-model.md` for the full verification workflow.

## Files

| File | Purpose |
|------|---------|
| `compose/main/10-ollama.yml` | Ollama service definition |
| `compose/main/00-networks-and-volumes.yml` | Shared networks (includes `ollama-bridge`) |
| `workspace/models/*.Modelfile` | Model definitions for Ollama |
| `scripts/entrypoint.ollama.sh` | Model sync + startup script (currently unused) |
| `workspace/models/models-config.yaml` | Model sync contract — drives `make models-sync` |

## Related Rules

- `.claude/rules/rebuild-model-after-modelfile-edit.md` — always rebuild after Modelfile changes
- `.claude/rules/verify-loaded-model.md` — verify loaded model before benchmarking
- `.claude/rules/compose-external-network-check.md` — verify external networks exist
