# vLLM Stack

Drop-in Ollama replacement: three vLLM engines behind a LiteLLM gateway on port 11434.

## Architecture

```
vllm-gateway (LiteLLM, :11434)
├── vllm-planner    → Qwen/Qwen3.6-35B-A3B-FP8   (multimodal, reasoning)
├── vllm-coder      → Qwen/Qwen3.6-27B-FP8        (reasoning)
└── vllm-fastcoder  → Qwen/Qwen3.5-4B              (multimodal)
```

Routes are configured in `workspace/vllm/litellm_config.yaml` by `hosted_vllm/` model type. LiteLLM forwards `/v1/chat/completions` requests to the matching backend based on `model` param.

## Mutual Exclusivity

The vLLM stack and main Ollama stack are **mutually exclusive** on port 11434. Stop one before starting the other:
```bash
make down-main && make up-vllm
# or
make down-vllm && make up-main
```

## VRAM Constraints (RTX 6000 Ada, 48 GB)

Models run **one at a time** due to VRAM limits — they share the same GPU:

| Model | Weights (~VRAM) | gpu-memory-utilization | Reason |
|-------|-----------------|------------------------|--------|
| Planner (Qwen3.6-35B-A3B-FP8) | ~38 GB | 0.92 | Largest; needs near-full budget |
| Coder (Qwen3.6-27B-FP8) | ~22 GB | 0.90 | Heavy but fits with headroom |
| FastCoder (Qwen3.5-4B) | ~8 GB | 0.85 | Small; generous KV cache for long contexts |

`gpu-memory-utilization` controls how much of the GPU vLLM can use for weights + KV cache. Lower values cause OOM on weight load because vLLM must fit the entire model in the allocated fraction.

## Optimization Flags

Applied per model via `VLLM_EXTRA_FLAGS`:

| Flag | Purpose | Models |
|------|---------|--------|
| `--attention-backend flashinfer` | FlashInfer kernel (RTX 6000 Ada = Ada Lovelace arch, fully supported) | Coder, FastCoder |
| `--enable-chunked-prefill` | Process long prompts in chunks, reducing peak KV cache memory | All |
| `--max-num-seqs 256` | Limit concurrent sequences (lower memory overhead vs default) | All |
| `--kv-cache-dtype fp8` | FP8 quantized KV cache (halves precision vs FP16 default) | All |
| `--mm-encoder-tp-mode data` | Multimodal encoder tensor parallelism | Planner, FastCoder |
| `--reasoning-parser qwen3` | Parse Qwen3 extended thinking tags | Planner, Coder |

**Why no FlashInfer on Planner?** The Planner is multimodal (Qwen3.6-35B-A3B). FlashInfer + multimodal encoders in vLLM have known compatibility issues — the safer default is `flash-attn` for this model. FastCoder has multimodal but is small enough that FlashInfer handles it without issue.

## Files

| File | Purpose |
|------|---------|
| `compose/vllm/Dockerfile.vllm` | Custom image (vllm-openai + huggingface_hub pinned) |
| `compose/vllm/10-vllm-planner.yml` | Planner engine service |
| `compose/vllm/20-vllm-coder.yml` | Coder engine service |
| `compose/vllm/30-vllm-fastcoder.yml` | FastCoder engine service |
| `compose/vllm/40-vllm-gateway.yml` | LiteLLM gateway |
| `compose/vllm/90-vllm-download.yml` | Pre-download services |
| `scripts/entrypoint.vllm.sh` | HF cache check → exec vllm serve |
| `workspace/vllm/litellm_config.yaml` | Gateway route config |
| `workspace/vllm/vllm-models.yaml` | Model registry (machine-readable) |

## Make Targets

```bash
make up-vllm              # Build + start all engines + gateway
make down-vllm            # Stop vLLM stack
make build-vllm           # Build custom image only
make ps-vllm              # List containers
make logs-vllm-planner    # Logs for specific engine
make restart-vllm-coder   # Restart specific engine
make download-vllm-models # Pre-download all models to ${MODELS}/vllm/
make smoke-vllm           # Validate config + pull upstream tags
```

## Version Tags

- **vLLM**: `v0.25.0-cu129-ubuntu2404` (format: `v<semver>-cu<cuda>-ubuntu<os>`)
- **LiteLLM**: `1.92.0`
- **huggingface_hub**: `0.35.0` (pinned in Dockerfile)

Versions set in `.env`. Update manager (`tools/update_manager.py`) discovers latest tags from Docker Hub / PyPI.
