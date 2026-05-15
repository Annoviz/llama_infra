# Docker Image Update Changelog - March 26, 2026

## Summary of Updates
This document outlines the Docker image and developer-experience updates applied to the `llama_infra` project, including version changes, build fixes, utility commands, and compatibility notes verified against upstream release/tag metadata on 2026-03-26.

## Version Updates

### 1. Ollama: 0.9.0 → 0.18.3
**Compatibility Notes:**
- Latest published release and Docker tag observed on 2026-03-26
- Existing `OLLAMA_*` environment variables remain valid in this repo config
- GPU-capable deployment wiring remains unchanged

### 2. AnythingLLM: 1.8.1 → 1.11.2
**Compatibility Notes:**
- Latest published release and Docker tag observed on 2026-03-26
- Existing Ollama integration variables in `docker-compose.yml` remain unchanged
- No compose-level config changes were required for this repo

### 3. Open WebUI: v0.6.13 → v0.8.11
**Compatibility Notes:**
- Latest published GitHub release observed on 2026-03-26
- The pinned GHCR image tag `v0.8.11` exists
- Existing `OLLAMA_BASE_URL` wiring in `docker-compose.yml` remains unchanged

### 4. llama.cpp image: full-cuda (unversioned) → full-cuda-b5350
**Compatibility Notes:**
- Latest published GHCR `full-cuda` image tag observed on 2026-03-26: `full-cuda-b5350`
- Upstream GitHub release tag is `b8533`, but GHCR `full-cuda` image tags use a different published tag sequence
- `full-cuda-b8533` is not a published image tag, so the repo pins the latest actual image tag instead
- CUDA-enabled image variant is preserved for both `llamacpp-server` and the Python build base image

### 5. llama-cpp-python: 0.3.7 → 0.3.19
**Compatibility Notes:**
- Latest published PyPI and GitHub release observed on 2026-03-26
- The repo pins `0.3.19` consistently in compose, Docker build args, and `workspace/requirements.txt`
- Existing server/config interfaces used by this repo remain unchanged at the compose surface

## Build and workflow improvements

- Added a top-level `Makefile` with utility commands for each service and stack
- Fixed `Dockerfile.llamacpp-server-python` to default to the versioned requirements file that actually exists: `requirements-llama_cpp_python-0.3.19.txt`
- Added `REQUIREMENTS_FILE` as an explicit env-overridable build arg in `docker-compose.llama.cpp.yml`
- Updated `README.md` to document strict pins, override variables, GPU checks, and Make-based workflows
- Replaced the legacy `requirements-llama_cpp_python-0.3.7.txt` file with `requirements-llama_cpp_python-0.3.19.txt`

## GPU Compatibility

✅ **GPU support verified for this repo configuration and local host:**
- Both llama.cpp services request NVIDIA devices via Compose GPU reservations
- Docker on the host exposes the `nvidia` runtime and uses it as the default runtime
- Local host GPU visibility is confirmed with `nvidia-smi` (`NVIDIA RTX A6000`, driver `580.126.09`, CUDA `13.0`)
- The pinned CUDA image tag exists: `ghcr.io/ggml-org/llama.cpp:full-cuda-b5350`

## Breaking Changes

**No compose-level breaking changes identified in this repo update.**

Notes:
- Environment-variable override behavior is preserved via `${VAR:-explicit_version}` defaults.
- The `llama.cpp` GitHub release tag and the published GHCR `full-cuda` image tag do not use the same numbering stream.

## Verification checklist

The finished repo state is validated with:

- `docker compose -f docker-compose.yml config`
- `docker compose -f docker-compose.llama.cpp.yml config`
- override rendering for `OLLAMA_VERSION`, `ANYTHINGLLM_VERSION`, `OW_VERSION`, `IMAGE`, `BASE_IMAGE`, `LLAMA_CPP_VERSION`, and `REQUIREMENTS_FILE`
- `docker compose -f docker-compose.llama.cpp.yml build llamacpp-server-py`
- `docker run --rm --gpus all --entrypoint nvidia-smi ghcr.io/ggml-org/llama.cpp:full-cuda-b5350`
- `make help`

## Latest verified defaults

- `ollama/ollama:0.18.3`
- `mintplexlabs/anythingllm:1.11.2`
- `ghcr.io/open-webui/open-webui:v0.8.11`
- `ghcr.io/ggml-org/llama.cpp:full-cuda-b5350`
- `llama-cpp-python==0.3.19`
- `requirements-dev.txt` (current active build input)

---
Generated: March 26, 2026

Update run (May 15, 2026):
- Applied version bumps from the update workflow in the tracked defaults.
- `ollama/ollama:${OLLAMA_VERSION:-0.18.3}` -> `ollama/ollama:${OLLAMA_VERSION:-0.24.0}` in `docker-compose.yml`.
- `mintplexlabs/anythingllm:${ANYTHINGLLM_VERSION:-1.11.2}` -> `mintplexlabs/anythingllm:${ANYTHINGLLM_VERSION:-1.12.1}` in `docker-compose.yml`.
- `LLAMA_CPP_VERSION` default `0.3.19` -> `0.3.23` in `docker-compose.llama.cpp.yml` and `Dockerfile.llamacpp-server-python`.
- Updated llama-cpp server support package minimums in `requirements-dev.txt`:
  - `diskcache>=5.6.1` -> `diskcache>=5.6.3`
  - `uvicorn>=0.22.0` -> `uvicorn>=0.47.0`
  - `fastapi>=0.100.0` -> `fastapi>=0.136.1`
  - `pydantic-settings>=2.0.1` -> `pydantic-settings>=2.14.1`
  - `sse-starlette>=1.6.1` -> `sse-starlette>=3.4.4`
  - `PyYAML>=5.1` -> `PyYAML>=6.0.3`
- No changes were applied in this run to Open WebUI pin (`v0.8.11`) or the llama.cpp CUDA base image tag (`full-cuda-b5350`).


