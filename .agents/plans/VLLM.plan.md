# vLLM Stack — Implementation Plan for llama_infra

> Adapted from the original AI-generated VLLM plan to match project conventions, naming, port layout, and directory structure. Gateway uses port **11434** (Ollama's default) as a drop-in replacement. All images use explicit version tags managed by `tools/update_manager.py`.

## 1. Goals

- Run **three** vLLM engines (Planner, Coder, FastCoder) side-by-side on a single **RTX 6000 Ada (48 GB VRAM)**.
- Leave **≥ 5 GB VRAM free** for the host kernel / other processes.
- Expose an **OpenAI-compatible API gateway on port 11434** — the same port Ollama uses — so Claude Code, Open WebUI, and existing curl aliases work with zero reconfiguration.
- All Docker images use **explicit version tags** (never `latest`), managed by the update script.
- Follow project conventions: split compose files, numbered naming, `Makefile` targets, env-var-driven config, shared network, dedicated entrypoint script for model pre-download, custom Dockerfiles where needed.

---

## 2. Model Selection & VRAM Budget

| Agent Role | HF Model | Format | gpu-memory-utilization | Est. VRAM | Max Context | Notes |
|---|---|---|---|---|---|---|
| **Planner** (vision + reasoning) | `Qwen/Qwen3.6-35B-A3B-FP8` | FP8 MoE native | 0.45 | ~21.6 GB | 16,384 | Multimodal (image+video), `--reasoning-parser qwen3`, MTP via `qwen3_next_mtp` |
| **Coder** (deep code gen) | `Qwen/Qwen3.6-27B-AWQ` | AWQ INT4 | 0.35 | ~17.2 GB | 8,192 | AWQ quantized, speculative MTP may be tested if compatible |
| **FastCoder** (boilerplate, fast turn) | `Qwen/Qwen3.5-4B` | FP16 native | 0.09 | ~4.4 GB | 4,096 | MoE + GDN hybrid attn, multimodal, tiny KV cache |

**Total allocated: ~89% (~42 GB). Buffer: ~11% (~5.4 GB) — exceeds the 5 GB minimum.**

> **Model name mapping** (project convention):
> - Planner → served as `planner`
> - Coder → served as `coder`
> - FastCoder → served as `fast-coder`

---

## 3. Port Allocation

The gateway uses **port 11434** — the same port Ollama serves on — so clients require zero reconfiguration (Claude Code, Open WebUI, curl aliases all default to `localhost:11434`). The vLLM stack and ollama-server are **mutually exclusive** on this port; stop one before starting the other.

| Service | Host Port | Container Port | Reasoning |
|---|---|---|---|
| `vllm-planner` | internal only (not published) | 8000 | Reaches via vllm-bridge network |
| `vllm-coder` | internal only (not published) | 8000 | Reaches via vllm-bridge network |
| `vllm-fastcoder` | internal only (not published) | 8000 | Reaches via vllm-bridge network |
| `vllm-gateway` (LiteLLM) | **11434** | 8000 | Unified entry point — drops in as Ollama replacement |

> Individual engine ports are not published — the gateway is the sole entry point.
> Gateway port is overridable via `VLLM_GATEWAY_PORT` if you need ollama + vLLM coexistence temporarily.

---

## 4. File Layout

```
compose/vllm/
├── 00-vllm-networks.yml            # vllm-bridge network only (no named volumes)
├── 05-vllm-engine-base.yml         # Shared base service (extends target)
├── 10-vllm-planner.yml              # Planner — extends engine-base, overrides env only
├── 20-vllm-coder.yml                # Coder — extends engine-base, overrides env only
├── 30-vllm-fastcoder.yml            # FastCoder — extends engine-base, overrides env only
├── 40-vllm-gateway.yml              # LiteLLM gateway (explicit version tag)
├── Dockerfile.vllm                  # Custom vLLM image w/ HF cache checker + entrypoint
├── Dockerfile.hf-downloader         # Unified HF model pre-download image
└── 90-vllm-download.yml             # Pre-download init services

scripts/
└── entrypoint.vllm.sh               # Model cache check → exec vllm serve

workspace/vllm/
├── litellm_config.yaml              # LiteLLM routing config
└── vllm-models.yaml                 # Model definitions (HF repo, served-name, flags)
```

---

## 5. Dockerfiles

### `compose/vllm/Dockerfile.vllm`

Custom vLLM image that bundles the HF cache checker and entrypoint script. Built from an explicitly versioned CUDA base — managed by update_manager.py via `${VLLM_VERSION}`.

```dockerfile
# syntax=docker/dockerfile:1
ARG VLLM_VERSION=0.25.0
FROM vllm/vllm-openai:${VLLM_VERSION}-cuda

LABEL maintainer="llama_infra" \
      org.opencontainers.image.source="https://github.com/user/llama_infra"

# Install huggingface_hub for cache checking at startup
RUN pip install --no-cache-dir "huggingface_hub>=0.29,<1.0"

# Entrypoint handles: (1) model cache check, (2) exec vllm serve
COPY scripts/entrypoint.vllm.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
```

### `compose/vllm/Dockerfile.hf-downloader`

Unified, lightweight image for pre-downloading any HF model. Used by the download profile services — one image, different args per model.

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim

ARG HUGGINGFACE_HUB_VERSION=0.35.0
LABEL maintainer="llama_infra"

RUN pip install --no-cache-dir "huggingface_hub==${HUGGINGFACE_HUB_VERSION}"

ENTRYPOINT ["huggingface-cli", "download", "--repo-type", "model"]
CMD ["--help"]
```

---

## 6. Compose Service Definitions

### `compose/vllm/00-vllm-networks.yml`

```yaml
networks:
  vllm-bridge:
    driver: bridge
```

> No named volumes — models are stored under `${MODELS}/vllm` (same parent dir as Ollama's `/models`). User-visible, user-controlled location.

### `compose/vllm/05-vllm-engine-base.yml`

Shared base service. All three engines extend this — only env vars and container_name differ per model. The `_engine-base` name is internal (not a runnable service).

```yaml
services:
  _vllm-engine-base:
    build:
      context: ..
      dockerfile: compose/vllm/Dockerfile.vllm
      args:
        VLLM_VERSION: ${VLLM_VERSION:-0.25.0}
    image: llama-infra-vllm:${VLLM_VERSION:-0.25.0}
    shm_size: "16gb"
    ulimits:
      memlock: -1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["${GPU_ID:-0}"]
              capabilities: [gpu]
    volumes:
      - ${MODELS:-./models}/vllm:/root/.cache/huggingface
    networks:
      - vllm-bridge
      - ollama-bridge  # cross-stack for gateway/WUI routing
    restart: always
    environment:
      HF_TOKEN: "${HF_TOKEN}"
      HUGGING_FACE_HUB_TOKEN: "${HF_TOKEN}"
      HF_HOME: "/root/.cache/huggingface"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/models"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 120s
```

### `compose/vllm/10-vllm-planner.yml`

Extends the base; overrides only container_name and model-specific env vars.

```yaml
services:
  vllm-planner:
    extends:
      file: 05-vllm-engine-base.yml
      service: _vllm-engine-base
    container_name: vllm-planner
    environment:
      HF_TOKEN: "${HF_TOKEN}"
      HUGGING_FACE_HUB_TOKEN: "${HF_TOKEN}"
      VLLM_MODEL_REPO: "Qwen/Qwen3.6-35B-A3B-FP8"
      VLLM_SERVED_NAME: "planner"
      VLLM_MAX_LEN: "16384"
      VLLM_GPU_MEM: "0.45"
      VLLM_EXTRA_FLAGS: "--mm-encoder-tp-mode data --reasoning-parser qwen3 --trust-remote-code"
```

### `compose/vllm/20-vllm-coder.yml`

```yaml
services:
  vllm-coder:
    extends:
      file: 05-vllm-engine-base.yml
      service: _vllm-engine-base
    container_name: vllm-coder
    environment:
      HF_TOKEN: "${HF_TOKEN}"
      HUGGING_FACE_HUB_TOKEN: "${HF_TOKEN}"
      VLLM_MODEL_REPO: "Qwen/Qwen3.6-27B-AWQ"
      VLLM_SERVED_NAME: "coder"
      VLLM_MAX_LEN: "8192"
      VLLM_GPU_MEM: "0.35"
      VLLM_EXTRA_FLAGS: "--quantization awq --trust-remote-code --reasoning-parser qwen3"
```

### `compose/vllm/30-vllm-fastcoder.yml`

```yaml
services:
  vllm-fastcoder:
    extends:
      file: 05-vllm-engine-base.yml
      service: _vllm-engine-base
    container_name: vllm-fastcoder
    environment:
      HF_TOKEN: "${HF_TOKEN}"
      HUGGING_FACE_HUB_TOKEN: "${HF_TOKEN}"
      VLLM_MODEL_REPO: "Qwen/Qwen3.5-4B"
      VLLM_SERVED_NAME: "fast-coder"
      VLLM_MAX_LEN: "4096"
      VLLM_GPU_MEM: "0.09"
      VLLM_EXTRA_FLAGS: "--trust-remote-code --mm-encoder-tp-mode data"
```

> **How it works:** Docker Compose resolves `extends` at load time (equivalent to YAML merge). Each engine inherits build, image, GPU reservation, volumes, networks, restart policy, and healthcheck from the base. Only `container_name` and per-model env vars are defined inline — exactly what differs between services.
> **Adding a fourth engine** is as simple as one new compose file with ~12 lines of YAML.

### `compose/vllm/40-vllm-gateway.yml`

LiteLLM uses an **explicit version tag** — managed by update_manager.py. Never `main` or `latest`.

```yaml
services:
  vllm-gateway:
    image: ghcr.io/berriai/litellm:${LITELLM_VERSION:-1.92.0}
    container_name: vllm-gateway
    ports:
      - "${VLLM_GATEWAY_PORT:-11434}:8000"
    volumes:
      - ./workspace/vllm/litellm_config.yaml:/app/config.yaml:ro
    networks:
      - vllm-bridge
      - ollama-bridge
    depends_on:
      vllm-planner:
        condition: service_healthy
      vllm-coder:
        condition: service_healthy
      vllm-fastcoder:
        condition: service_healthy
    restart: always
    command: ["--config", "/app/config.yaml", "--port", "8000", "--host", "0.0.0.0"]
```

### `compose/vllm/90-vllm-download.yml` (pre-download)

Uses the unified HF downloader image for all three models — one Dockerfile, different CMDs:

```yaml
services:
  vllm-download-planner:
    build:
      context: ..
      dockerfile: compose/vllm/Dockerfile.hf-downloader
    image: llama-infra-hf-downloader:${HF_DOWNLOADER_VERSION:-0.1.0}
    container_name: vllm-dl-planner
    environment:
      HF_TOKEN: "${HF_TOKEN}"
      HUGGING_FACE_HUB_TOKEN: "${HF_TOKEN}"
      HF_HOME: "/root/.cache/huggingface"
    volumes:
      - ${MODELS:-./models}/vllm:/root/.cache/huggingface
    command: ["Qwen/Qwen3.6-35B-A3B-FP8"]
    profiles: ["download"]

  vllm-download-coder:
    image: llama-infra-hf-downloader:${HF_DOWNLOADER_VERSION:-0.1.0}
    container_name: vllm-dl-coder
    environment:
      HF_TOKEN: "${HF_TOKEN}"
      HUGGING_FACE_HUB_TOKEN: "${HF_TOKEN}"
      HF_HOME: "/root/.cache/huggingface"
    volumes:
      - ${MODELS:-./models}/vllm:/root/.cache/huggingface
    command: ["Qwen/Qwen3.6-27B-AWQ"]
    profiles: ["download"]

  vllm-download-fastcoder:
    image: llama-infra-hf-downloader:${HF_DOWNLOADER_VERSION:-0.1.0}
    container_name: vllm-dl-fastcoder
    environment:
      HF_TOKEN: "${HF_TOKEN}"
      HUGGING_FACE_HUB_TOKEN: "${HF_TOKEN}"
      HF_HOME: "/root/.cache/huggingface"
    volumes:
      - ${MODELS:-./models}/vllm:/root/.cache/huggingface
    command: ["Qwen/Qwen3.5-4B"]
    profiles: ["download"]
```

> Download services use a `download` profile — run with `-p download` to trigger.
> They exit after completion; models stay on disk at `${MODELS}/vllm/`.

---

## 7. Entrypoint Script: `scripts/entrypoint.vllm.sh`

A dedicated entrypoint that **pre-downloads** the model (if not already cached), then launches vLLM with the configured flags. This replaces the fragile Alpine sidecar approach and follows the project's pattern of `scripts/entrypoint.*.sh`.

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO="${VLLM_MODEL_REPO:?MODEL_REPO not set}"
SERVED="${VLLM_SERVED_NAME:?SERVED_NAME not set}"
MAX_LEN="${VLLM_MAX_LEN:-8192}"
GPU_MEM="${VLLM_GPU_MEM:-0.45}"
EXTRA="${VLLM_EXTRA_FLAGS:-}"

echo "[vllm-entrypoint] Ensuring model ${REPO} is cached..."
python3 -c "
from huggingface_hub import scan_cache_dir
cache = scan_cache_dir()
repos = {r.repo_id for r in cache.repos}
target = '${REPO}'
if target not in repos:
    from huggingface_hub import snapshot_download
    print(f'[vllm-entrypoint] Downloading {target}...')
    snapshot_download(repo_id=target, repo_type='model')
    print('[vllm-entrypoint] Download complete.')
else:
    print(f'[vllm-entrypoint] {target} already cached — skipping download.')
"

echo "[vllm-entrypoint] Starting vLLM: ${REPO} as '${SERVED}' (gpu_mem=${GPU_MEM}, max_len=${MAX_LEN})"

exec vllm serve \
    "${REPO}" \
    --port 8000 \
    --max-model-len "${MAX_LEN}" \
    --gpu-memory-utilization "${GPU_MEM}" \
    --served-model-name "${SERVED}" \
    ${EXTRA}
```

---

## 8. LiteLLM Gateway Config: `workspace/vllm/litellm_config.yaml`

Routes by project model names (`planner`, `coder`, `fast-coder`) to the correct vLLM backends.

```yaml
model_list:
  - model_name: planner
    litellm_params:
      model: hosted_vllm/planner
      api_base: http://vllm-planner:8000/v1

  - model_name: coder
    litellm_params:
      model: hosted_vllm/coder
      api_base: http://vllm-coder:8000/v1

  - model_name: fast-coder
    litellm_params:
      model: hosted_vllm/fast-coder
      api_base: http://vllm-fastcoder:8000/v1

litellm_settings:
  drop_unsupported_params: true
```

> The gateway exposes a **single OpenAI-compatible endpoint** at `http://localhost:11434/v1`.
> Clients set `model=planner|coder|fast-coder` to route.

---

## 9. Model Definition File: `workspace/vllm/vllm-models.yaml`

A machine-readable model registry (mirrors `models-config.yaml` pattern):

```yaml
# vLLM model definitions
# Used by entrypoint.vllm.sh and update-manager for model tracking.
models:
  - id: planner
    served_name: planner
    hf_repo: Qwen/Qwen3.6-35B-A3B-FP8
    format: fp8
    gpu_memory_utilization: 0.45
    max_model_len: 16384
    multimodal: true
    extra_flags: "--mm-encoder-tp-mode data --reasoning-parser qwen3 --trust-remote-code"

  - id: coder
    served_name: coder
    hf_repo: Qwen/Qwen3.6-27B-AWQ
    format: awq-int4
    gpu_memory_utilization: 0.35
    max_model_len: 8192
    multimodal: false
    extra_flags: "--quantization awq --trust-remote-code --reasoning-parser qwen3"

  - id: fast-coder
    served_name: fast-coder
    hf_repo: Qwen/Qwen3.5-4B
    format: fp16
    gpu_memory_utilization: 0.09
    max_model_len: 4096
    multimodal: true
    extra_flags: "--trust-remote-code --mm-encoder-tp-mode data"
```

---

## 10. Update Manager Integration

### New version constants in `.env`:

```bash
# vLLM stack — managed by tools/update_manager.py
VLLM_VERSION=0.25.0              # PyPI: vllm (DockerHub: vllm/vllm-openai:<ver>-cuda)
LITELLM_VERSION=1.92.0           # PyPI: litellm  (GHCR: ghcr.io/berriai/litellm:<ver>)
HF_DOWNLOADER_VERSION=0.1.0      # Internal build version (Dockerfile.hf-downloader)
```

### `tools/update_manager.py` additions

New file paths to track at top of file:

```python
DOCKER_COMPOSE_VLLM_PLANNER = ROOT / "compose/vllm/10-vllm-planner.yml"
DOCKER_COMPOSE_VLLM_GATEWAY = ROOT / "compose/vllm/40-vllm-gateway.yml"
DOCKERFILE_VLLM = ROOT / "compose/vllm/Dockerfile.vllm"
DOCKERFILE_HF_DOWNLOADER = ROOT / "compose/vllm/Dockerfile.hf-downloader"
```

New discovery targets in `discover_docker_updates()`:

| Target | Registry | Pattern | Source file(s) | Env var |
|---|---|---|---|---|
| **vLLM** (CUDA image) | Docker Hub `vllm/vllm-openai` | `<semver>-cuda` tag, e.g. `0.25.0-cuda` | `Dockerfile.vllm` ARG + compose defaults | `${VLLM_VERSION}` |
| **LiteLLM** | PyPI `litellm` (stable only) | Semver `X.Y.Z`, exclude pre-releases (`rc`, `dev`, `a`) | `40-vllm-gateway.yml` default | `${LITELLM_VERSION}` |

New discovery logic (pseudocode for update_manager.py):

```python
# vLLM — check Docker Hub for latest <semver>-cuda tag
if True:  # vllm files exist
    vllm_text = DOCKERFILE_VLLM.read_text(encoding="utf-8")
    current_vllm = re.search(r"ARG VLLM_VERSION=(\d+\.\d+\.\d+)", vllm_text)
    if current_vllm:
        try:
            tags = docker_hub_tags("vllm/vllm-openai")
            # Match semver-cuda tags: 0.25.0-cuda, 0.24.0-cuda, etc.
            cuda_tags = [t.replace("-cuda", "") for t in tags if re.match(r"^\d+\.\d+\.\d+-cuda$", t)]
            latest = sorted(cuda_tags, key=version_key)[-1]
        except ...:
            latest = None
        if latest:
            items.append(UpdateItem(
                kind="docker", name="vllm/vllm-openai (CUDA)",
                source_file=DOCKERFILE_VLLM, current=current_vllm.group(1),
                latest=latest, applyable=is_newer(latest, current_vllm.group(1)),
                reason="Docker Hub semver-cuda tag",
            ))

# LiteLLM — check PyPI for latest stable version (no pre-releases)
if True:  # gateway file exists
    gw_text = DOCKER_COMPOSE_VLLM_GATEWAY.read_text(encoding="utf-8")
    current_litellm = re.search(r"\$\{LITELLM_VERSION:-([^}]+)\}", gw_text)
    if current_litellm:
        try:
            latest = latest_pypi_version("litellm")
            # Strip pre-release suffixes — only apply stable versions
            if latest and not re.search(r"(rc|dev|a|b|alpha|beta)", latest, re.I):
                pass  # stable version found
            else:
                latest = None  # skip pre-releases
        except ...:
            latest = None
        if latest:
            items.append(UpdateItem(
                kind="docker", name="ghcr.io/berriai/litellm",
                source_file=DOCKER_COMPOSE_VLLM_GATEWAY,
                current=current_litellm.group(1),
                latest=latest, applyable=is_newer(latest, current_litellm.group(1)),
                reason="PyPI (stable only)",
            ))
```

New replacement rules in `build_replacements()`:

```python
elif item.name == "vllm/vllm-openai (CUDA)":
    # Update Dockerfile ARG
    replacements.append(Replacement(
        source_file=DOCKERFILE_VLLM,
        old=f"ARG VLLM_VERSION={item.current}",
        new=f"ARG VLLM_VERSION={item.latest}",
    ))
    # Update compose file build args defaults (planner, coder, fastcoder)
    for cf in [DOCKER_COMPOSE_VLLM_PLANNER]:  # + other vllm compose files if needed
        replacements.append(Replacement(
            source_file=cf,
            old=f'VLLM_VERSION: ${{VLLM_VERSION:-{item.current}}}',
            new=f'VLLM_VERSION: ${{VLLM_VERSION:-{item.latest}}}',
        ))
        replacements.append(Replacement(
            source_file=cf,
            old=f'image: llama-infra-vllm:{item.current}',  # if hardcoded fallback
            new=f'image: llama-infra-vllm:{item.latest}',
        ))

elif item.name == "ghcr.io/berriai/litellm":
    replacements.append(Replacement(
        source_file=DOCKER_COMPOSE_VLLM_GATEWAY,
        old=r"${LITELLM_VERSION:-" + item.current + "}",
        new=r"${LITELLM_VERSION:-" + item.latest + "}",
    ))
```

### Update manager behavior notes:
- **vLLM**: Queries Docker Hub for `vllm/vllm-openai` tags matching `<semver>-cuda`. Strips `-cuda` suffix to extract the semver. Reports against `ARG VLLM_VERSION=...` in the Dockerfile. On apply, updates both the Dockerfile ARG and compose file fallback defaults.
- **LiteLLM**: Queries PyPI for `litellm`, skips pre-releases (`rc`, `dev`). Updates the gateway compose file default. Never applies unstable versions.

---

## 11. Makefile Integration

```makefile
# vLLM stack compose assembly
COMPOSE_VLLM := docker compose --project-directory $(CURDIR) \
    -f compose/vllm/00-vllm-networks.yml \
    -f compose/vllm/05-vllm-engine-base.yml \
    -f compose/vllm/10-vllm-planner.yml \
    -f compose/vllm/20-vllm-coder.yml \
    -f compose/vllm/30-vllm-fastcoder.yml \
    -f compose/vllm/40-vllm-gateway.yml

COMPOSE_VLLM_DL := docker compose --project-directory $(CURDIR) \
    -f compose/vllm/00-vllm-networks.yml \
    -f compose/vllm/90-vllm-download.yml

# Build (custom Dockerfiles)
build-vllm:
    $(COMPOSE_VLLM) build --pull vllm-planner vllm-coder vllm-fastcoder

build-vllm-downloader:
    $(COMPOSE_VLLM_DL) build

# Config / pull
config-vllm:
    $(COMPOSE_VLLM) config

pull-vllm-base:
    docker pull vllm/vllm-openai:${VLLM_VERSION:-0.25.0}-cuda
    docker pull ghcr.io/berriai/litellm:${LITELLM_VERSION:-1.92.0}

# Lifecycle — vLLM and Ollama are mutually exclusive (both bind 11434).
up-vllm: build-vllm
    $(COMPOSE_VLLM) up -d

down-vllm:
    $(COMPOSE_VLLM) down

download-vllm-models: build-vllm-downloader
    $(COMPOSE_VLLM_DL) --profile download up --remove-orphans

# Individual services
up-vllm-planner: build-vllm
    $(COMPOSE_VLLM) up -d vllm-planner

up-vllm-coder: build-vllm
    $(COMPOSE_VLLM) up -d vllm-coder

up-vllm-fastcoder: build-vllm
    $(COMPOSE_VLLM) up -d vllm-fastcoder

# Diagnostics
ps-vllm:
    $(COMPOSE_VLLM) ps

logs-vllm-planner:
    $(COMPOSE_VLLM) logs -f --tail=200 vllm-planner

logs-vllm-coder:
    $(COMPOSE_VLLM) logs -f --tail=200 vllm-coder

logs-vllm-fastcoder:
    $(COMPOSE_VLLM) logs -f --tail=200 vllm-fastcoder

logs-vllm-gateway:
    $(COMPOSE_VLLM) logs -f --tail=200 vllm-gateway

restart-vllm-planner:
    $(COMPOSE_VLLM) restart vllm-planner

restart-vllm-coder:
    $(COMPOSE_VLLM) restart vllm-coder

restart-vllm-fastcoder:
    $(COMPOSE_VLLM) restart vllm-fastcoder
```

Also update existing aggregate targets (`ps-all`, `logs-all`, `down-all`, `pull-all`) to include the vLLM stack.

---

## 12. `.env` Additions

```bash
# vLLM stack — managed by tools/update_manager.py
VLLM_VERSION=0.25.0              # PyPI: vllm (DockerHub: vllm/vllm-openai:<ver>-cuda)
LITELLM_VERSION=1.92.0           # PyPI: litellm  (GHCR: ghcr.io/berriai/litellm:<ver>)
HF_DOWNLOADER_VERSION=0.1.0      # Internal build version (Dockerfile.hf-downloader)
VLLM_GATEWAY_PORT=11434          # Same as Ollama — mutually exclusive stacks
HF_TOKEN=<your-huggingface-token>  # Required for gated models
```

---

## 13. Implementation Steps (Ordered)

### Phase 1: Dockerfiles + scripts
1. Create `compose/vllm/` directory.
2. Write `Dockerfile.vllm` (vLLM engine image with HF cache checker).
3. Write `Dockerfile.hf-downloader` (unified HF model downloader).
4. Write `scripts/entrypoint.vllm.sh` (chmod +x).

### Phase 2: Compose files + configs
5. Write `00-vllm-networks.yml`.
6. Write `10-vllm-planner.yml`, `20-vllm-coder.yml`, `30-vllm-fastcoder.yml`.
7. Write `40-vllm-gateway.yml` (explicit LiteLLM version).
8. Write `90-vllm-download.yml`.
9. Write `workspace/vllm/litellm_config.yaml`.
10. Write `workspace/vllm/vllm-models.yaml`.

### Phase 3: Makefile
11. Add all vLLM targets (build, config, lifecycle, diagnostics).
12. Update aggregate targets (`ps-all`, `down-all`, etc.).
13. Update `help-verbose` output with vLLM section.

### Phase 4: Update manager
14. Add file path constants for vLLM files to `update_manager.py`.
15. Add vLLM (Docker Hub `-cuda` tag) discovery logic.
16. Add LiteLLM (PyPI stable-only) discovery logic.
17. Add replacement rules for both targets in `build_replacements()`.
18. Test: `make updates-check` should report vLLM and LiteLLM versions.

### Phase 5: Environment + docs
19. Document `.env` additions (add commented-out examples).
20. Update `README.md` with vLLM stack section.
21. Add `CHANGELOG.md` entry.
22. Update `CLAUDE.md` architecture snapshot (third stack).

### Phase 6: Validation
23. Run `make config-vllm` — verify compose renders cleanly.
24. Run `make build-vllm` — build custom images.
25. Set `HF_TOKEN`, run `make download-vllm-models` — pre-cache weights.
26. Stop Ollama (`make down-main`), then `make up-vllm`.
27. Verify with `nvidia-smi` — VRAM allocation matches budget (~42 GB used, ~5.4 GB free).
28. Test gateway: `curl http://localhost:11434/v1/models` — should list planner, coder, fast-coder.
29. Smoke-test each engine via `/v1/completions`.
30. Run `make verify-agent-routing`.

---

## 14. Key Design Decisions & Rationale

| Decision | Rationale |
|---|---|
| **Gateway on port 11434** | Zero client reconfiguration — Claude Code, Open WebUI, curl aliases all default to `localhost:11434`. vLLM stack is a drop-in Ollama replacement. |
| **Engines not published** | Individual vLLM engines are internal-only; the gateway (LiteLLM) is the sole entry point. Reduces attack surface and port clutter. |
| **Mutual exclusivity with Ollama** | Both bind 11434. User stops Ollama first (`make down-main`). Override via `VLLM_GATEWAY_PORT` if coexistence needed. |
| **Custom Dockerfile.vllm** | Bundles HF cache checker + entrypoint in one image; built from explicitly versioned CUDA base — no `latest` drift risk. Matches project pattern (cf. `Dockerfile.llamacpp-server-python`). |
| **Unified Dockerfile.hf-downloader** | Single lightweight image for all model downloads. Replaces ad-hoc Alpine/python containers. Version is internal (`HF_DOWNLOADER_VERSION`) and bumped only when the Dockerfile changes. |
| **Explicit version tags everywhere** | `VLLM_VERSION=0.25.0`, `LITELLM_VERSION=1.92.0` — no `latest`. All managed by update_manager.py. Prevents silent breaking changes. |
| **`extends` for engine services** | All three engines share build, image, GPU reservation, volumes, networks, healthcheck via a single base service (`05-vllm-engine-base.yml`). Each engine file is ~12 lines of overrides (container_name + env). Adding a fourth engine is one new file. |
| **Split compose files** (`compose/vllm/`) | Matches project convention (main, llama stacks both use split files). Numbered prefix for load order. |
| **`${MODELS}/vllm` bind mount** | Models stored under `${MODELS}/vllm/` (same parent dir as Ollama's `/models`). User-visible, user-controlled location — no Docker named volume magic. Matches project convention. |
| **Cross-network attach (`ollama-bridge`)** | Enables Open WebUI / AnythingLLM to reach vLLM backends without port publishing if desired. |
| **LiteLLM as gateway** | Single OpenAI-compatible endpoint; clients only need one base URL + model name routing. Stable version from PyPI (pre-releases skipped). |
| **`healthcheck` on engines, gateway depends on `service_healthy`** | Gateway won't start until all 3 vLLM engines are ready — prevents 503s during boot. |
| **No speculative decoding on Coder by default** | AWQ quantized models may not support MTP draft networks reliably; mark as experimental opt-in via `VLLM_EXTRA_FLAGS`. |
| **`--mm-encoder-tp-mode data` on Planner + FastCoder** | Both Qwen3.6-35B and Qwen3.5-4B are multimodal — this flag ensures the vision encoder loads correctly in vLLM. |

---

## 15. Known Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Port 11434 conflict with Ollama | User stops Ollama first (`make down-main`). Override via `VLLM_GATEWAY_PORT`. |
| `HF_TOKEN` not set → gated model download fails | Entrypoint script errors out with clear message; `.env` docs call it out. |
| VRAM OOM if context spikes | Hard `--gpu-memory-utilization` caps + vLLM internal queueing (no silent overflow). |
| AWQ MTP speculative decoding incompatibility | Not enabled by default; opt-in via env var if user wants to experiment. |
| Disk space for HF cache (~60 GB for 3 models) | Models land in `${MODELS}/vllm/` — user can see, move, or symlink to another drive as needed. |
| vLLM/LiteLLM version drift | Explicit version tags in `.env` + Dockerfile ARGs. Update manager checks and applies stable versions only. |
| Custom image build time on startup | `make up-vllm` depends on `build-vllm`. Docker layer caching makes rebuilds fast unless base tag changes. |

---

## 16. Client Configuration Examples

### Claude Code (no change needed — uses port 11434)

```bash
# Gateway is on 11434 — same as Ollama default.
# If using OpenAI protocol:
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=dummy  # LiteLLM doesn't require auth by default

# Then use /model planner, /model coder, or /model fast-coder
```

### Open WebUI (internal network — no port change)

When both stacks share `ollama-bridge`, Open WebUI can reach the gateway internally:
```bash
- OLLAMA_BASE_URL=http://vllm-gateway:8000/v1
```
Or externally via 11434 when only vLLM is running:
```bash
- OLLAMA_BASE_URL=http://localhost:11434/v1
```

> **Note:** LiteLLM speaks the OpenAI API protocol, not the native Ollama protocol.
> Clients that call `/api/generate` or `/api/chat` (Ollama-specific endpoints) will get 404s.
> Clients using `/v1/completions` or `/v1/chat/completions` (OpenAI standard) work directly.

---

## 17. Estimated Disk Requirements

| Component | Approx. Size |
|---|---|
| Qwen3.6-35B-A3B-FP8 | ~20 GB (FP8 compressed) |
| Qwen3.6-27B-AWQ | ~16 GB (AWQ INT4) |
| Qwen3.5-4B | ~8 GB (FP16) |
| **Total HF cache** | **~44–60 GB** (depends on revision, tokenizer overhead) |
| Docker images (vLLM CUDA + LiteLLM + downloader) | ~12 GB |

Models land in `${MODELS}/vllm/` (default: `./models/vllm/`). Ensure that drive has ≥ 75 GB free for headroom.\n\nIf your models dir is on a separate data drive (as in the default `.env`: `/mnt/data/workspaces/llama_infra/models`), vLLM weights will coexist alongside Ollama GGUFs — making it easy to compare performance between engines.
