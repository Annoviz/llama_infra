# Docker Image Update Changelog - March 26, 2026

## vLLM Stack — Added (July 13, 2026)

**New infrastructure:** A third Docker stack running three vLLM engines behind a LiteLLM gateway on port 11434 (drop-in Ollama replacement).

### New Components
- **vLLM Planner** (`Qwen/Qwen3.6-35B-A3B-FP8`, FP8 MoE, ~21.6 GB VRAM) — multimodal + reasoning
- **vLLM Coder** (`Qwen/Qwen3.6-27B-AWQ`, AWQ INT4, ~17.2 GB VRAM) — deep code generation
- **vLLM FastCoder** (`Qwen/Qwen3.5-4B`, FP16, ~4.4 GB VRAM) — fast boilerplate turns
- **LiteLLM Gateway** — OpenAI-compatible API on port 11434; routes by model name

### New Files
- `compose/vllm/` — Dockerfiles, split compose files (networks, engine base, planner, coder, fastcoder, gateway, download)
- `scripts/entrypoint.vllm.sh` — HF cache check → vLLM serve entrypoint
- `workspace/vllm/litellm_config.yaml` — LiteLLM routing config
- `workspace/vllm/vllm-models.yaml` — Machine-readable model registry

### Makefile Targets
- `make up-vllm`, `down-vllm`, `build-vllm`, `config-vllm`, `ps-vllm`, `logs-vllm-*`, `restart-vllm-*`
- `make download-vllm-models` — pre-download HF models to `${MODELS}/vllm/`

### Update Manager
- New targets: `vllm/vllm-openai (CUDA)` and `ghcr.io/berriai/litellm`
- Checks Docker Hub for `<semver>-cuda` tags; PyPI for stable LiteLLM versions only

## Docker Image Updates - July 09, 2026

**Note:** Each update was manually approved by the user via interactive prompt.


### Updated Docker Images

- **ollama/ollama**: `0.31.1` → `0.31.2`

### Updated Python Packages

- **llama-cpp-python[server]**: `0.3.32` → `0.3.33`
- **uvicorn**: `0.49.0` → `0.51.0`
- **hypothesis**: `6.155.7` → `6.156.4`

---

## Docker Image Updates - July 02, 2026

**Note:** Each update was manually approved by the user via interactive prompt.


### Updated Docker Images

- **ollama/ollama**: `0.30.11` → `0.31.1`
- **falkordb/mcpserver**: `1.2.2` → `1.3.0`

### Updated Python Packages

- **llama-cpp-python[server]**: `0.3.31` → `0.3.32`
- **fastapi**: `0.138.1` → `0.139.0`

---

## Docker Image Updates - June 27, 2026

**Note:** Each update was manually approved by the user via interactive prompt.


### Updated Docker Images

- **ollama/ollama**: `0.30.9` → `0.30.11`
- **mintplexlabs/anythingllm**: `1.14.1` → `1.15.0`
- **falkordb/falkordb**: `v4.18.10` → `v4.18.11`

### Updated Python Packages

- **llama-cpp-python[server]**: `0.3.30` → `0.3.31`
- **notebook**: `7.5.7` → `7.6.0`
- **fastapi**: `0.137.1` → `0.138.1`
- **pydantic-settings**: `2.14.1` → `2.14.2`
- **sse-starlette**: `3.4.4` → `3.4.5`
- **pytest**: `9.1.0` → `9.1.1`
- **hypothesis**: `6.155.3` → `6.155.7`
- **ruff**: `0.15.17` → `0.15.20`

---

## Docker Image Updates - June 17, 2026

**Note:** Each update was manually approved by the user via interactive prompt.


### Updated Docker Images

- **ollama/ollama**: `0.30.8` → `0.30.9`
- **mintplexlabs/anythingllm**: `1.12.1` → `1.14.1`
- **falkordb/falkordb**: `v4.18.9` → `v4.18.10`

### Updated Python Packages

- **llama-cpp-python[server]**: `0.3.23` → `0.3.30`
- **jupyter-server**: `2.18.0` → `2.20.0`
- **notebook**: `7.5.6` → `7.5.7`
- **aiohttp**: `3.13.4` → `3.14.1`
- **uvicorn**: `0.47.0` → `0.49.0`
- **fastapi**: `0.136.1` → `0.137.1`
- **pytest**: `7.0.0` → `9.1.0`
- **pytest-asyncio**: `0.20.0` → `1.4.0`
- **pytest-cov**: `3.0.0` → `7.1.0`
- **pytest-mock**: `3.0.0` → `3.15.1`
- **pytest-xdist**: `3.0.0` → `3.8.0`
- **hypothesis**: `6.0.0` → `6.155.3`
- **pre-commit**: `4.0.0` → `4.6.0`
- **ruff**: `0.6.0` → `0.15.17`
- **black**: `24.0.0` → `26.5.1`

---


## Unsloth Optional Service - June 10, 2026

### Added

- Added optional Unsloth compose service at `compose/main/60-unsloth.yml`.
- Added Unsloth Make lifecycle targets:
  - `config-unsloth`, `pull-unsloth`
  - `up-unsloth`, `down-unsloth`
  - `restart-unsloth`, `logs-unsloth`, `ps-unsloth`

### Changed

- Added Unsloth compose fragment to `COMPOSE_MAIN` and `up-main-all` so full-stack startup includes Unsloth.
- Expanded `config-all`, `pull-all`, and `ps-all` to include Unsloth workflow commands.
- Updated `README.md` with Unsloth usage, compose layout entry, and default env settings.

### Defaults

- Unsloth image pinned to:
  - `unsloth/unsloth:2026.5.9-pt2.10.0-vllm-0.16.0-cu12.8-studio-release-v0.1.43-beta-2026-MAY-31`
- Host ports:
  - Jupyter: `localhost:8888`
  - API: `localhost:8000`

### Notes

- Service remains optional and does not change `make up-main` behavior.
- GPU access is configured via Docker Compose device capabilities (`capabilities: [gpu]`).

## FalkorDB MCP + Split Compose Update - June 8, 2026

### Added

- Added split main-stack compose files under `compose/main/`:
  - `00-networks-and-volumes.yml`
  - `10-ollama.yml`
  - `20-anythingllm.yml`
  - `30-open-webui.yml`
  - `40-falkordb.yml`
  - `50-falkordb-mcp.yml`
- Added local FalkorDB service (`falkordb/falkordb`) with persistence (`falkordb-data`) and healthcheck.
- Added FalkorDB MCP service (`falkordb/mcpserver`) configured in HTTP transport mode.

### Changed

- Refactored `Makefile` compose orchestration to combine per-component files instead of relying on a single monolithic main compose file.
- Removed obsolete top-level `docker-compose.yml` after migrating all active workflows to split compose files and Make targets.
- Added Falkor-specific lifecycle targets:
  - `config-falkor`, `pull-falkor`
  - `up-falkordb`, `up-falkordb-mcp`, `up-main-all`
  - `down-falkor`
  - `restart-falkordb`, `restart-falkordb-mcp`
  - `logs-falkordb`, `logs-falkordb-mcp`
  - `ps-falkor`
- Updated `README.md` with FalkorDB and FalkorDB MCP usage and split-compose layout guidance.

### Defaults

- FalkorDB server: `localhost:6379` (DB), `localhost:3000` (browser)
- FalkorDB MCP HTTP endpoint: `localhost:3005` -> container `3000`

### Notes

- Request text referenced "falcordb"; implementation uses official FalkorDB images and naming (`falkordb/*`).

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
- Fixed `compose/llama/Dockerfile.llamacpp-server-python` to default to the versioned requirements file that actually exists: `requirements-llama_cpp_python-0.3.19.txt`
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
- `LLAMA_CPP_VERSION` default `0.3.19` -> `0.3.23` in `docker-compose.llama.cpp.yml` and `compose/llama/Dockerfile.llamacpp-server-python`.
- Updated llama-cpp server support package minimums in `requirements-dev.txt`:
  - `diskcache>=5.6.1` -> `diskcache>=5.6.3`
  - `uvicorn>=0.22.0` -> `uvicorn>=0.47.0`
  - `fastapi>=0.100.0` -> `fastapi>=0.136.1`
  - `pydantic-settings>=2.0.1` -> `pydantic-settings>=2.14.1`
  - `sse-starlette>=1.6.1` -> `sse-starlette>=3.4.4`
  - `PyYAML>=5.1` -> `PyYAML>=6.0.3`
- No changes were applied in this run to Open WebUI pin (`v0.8.11`) or the llama.cpp CUDA base image tag (`full-cuda-b5350`).

## Agent Routing Update - May 15, 2026

### Added

- Added Markdown-based subagent specs under `.github/agents/`:
  - `.github/agents/README.md`
  - `.github/agents/docker-ops-agent.md`
  - `.github/agents/model-config-agent.md`
  - `.github/agents/update-manager-agent.md`
  - `.github/agents/docs-sync-agent.md`
- Added subagent docs checker script: `tools/check_agent_docs.py`.
- Added unit tests for docs checker: `tests/test_agent_docs_check.py`.
- Added CI workflow for docs checker: `.github/workflows/agents-docs-check.yml`.

### Changed

- Refactored `AGENTS.md` into a top-level orchestrator/router.
- Moved detailed task guidance from `AGENTS.md` into specialized subagent files.
- Added dual routing behavior:
  - manual explicit subagent routing,
  - proactive keyword/intent routing.
- Added strict proactive routing guidance with a keyword scoring table and tie-break rules in `AGENTS.md`.
- Added a required `## Example Prompt` section to each subagent markdown file.
- Added fallback policy for ambiguous and multi-domain tasks.

### Documentation

- Updated `README.md` with a new "Copilot subagents" section covering:
  - discovery convention (`.github/agents/*.md`),
  - available subagents,
  - manual and proactive routing examples,
  - fallback behavior.

### Follow-up Refinements (May 15, 2026)

- Updated `tools/check_agent_docs.py` to include `.github/agents/README.md` in validation.
- Reworked `.github/agents/README.md` to conform to the same required heading contract.
- Updated strict routing score weights in `AGENTS.md` to explicit 0-5 values.
- Added `make check-agent-docs` target in `Makefile` and aligned docs/CI to use it.

### Additional Hardening (May 15, 2026)

- Added `make verify-agent-routing` to run `check-agent-docs` plus `tests/test_agent_docs_check.py`.
- Added local pre-commit hooks for `check-agent-docs` and routing checker tests.
- Expanded checker tests with deterministic malformed-heading assertions.
- Updated CI workflow to run `make verify-agent-routing`.
- Added proactive routing minimum confidence threshold guidance in `AGENTS.md` (`>= 5` to auto-route).

### Subagent Expansion (May 15, 2026)

- Added `.github/agents/coding-agent.md` for implementation/refactor/test tasks.
- Added `.github/agents/reviewer-agent.md` for review/risk/regression-focused tasks.
- Added `.github/agents/commit-agent.md` for git commit/push workflows.
- Updated `AGENTS.md` manual examples and proactive keyword table to route the new agents.
- Updated subagent indexes in `.github/agents/README.md` and `README.md`.

### Agent Workflow Improvements (May 15, 2026)

- Added `.github/agents/routing-smoke.md` with manual/proactive routing smoke cases.
- Added explicit "when not to use this agent" boundaries across execution subagents.
- Pruned overlapping trigger wording between `coding-agent` and `reviewer-agent` guidance.
- Updated docs references in `.github/agents/README.md` and `README.md`.

### Agent Workflow Improvements - Follow-up (May 15, 2026)

- Enhanced `tools/check_agent_docs.py` to verify that concrete `.github/agents/*.md` paths referenced in `AGENTS.md` exist.
- Added checker tests for router path extraction and missing-path failures.
- Expanded `.github/agents/routing-smoke.md` with negative routing cases for each execution subagent.

### Agent Workflow Improvements - Follow-up 2 (May 15, 2026)

- Enhanced `tools/check_agent_docs.py` to fail on duplicate concrete subagent path references in `AGENTS.md`.
- Added checker tests for duplicate path detection and clarification-smoke coverage.
- Added an explicit clarification-question smoke case in `.github/agents/routing-smoke.md`.
- Added a monthly keyword drift review note in `.github/agents/README.md`.

### Model Sync and Entrypoint Split (May 15, 2026)

- Renamed llama.cpp Python entrypoint to `entrypoint.llamacpp.sh` and kept `llama_cpp.server` startup behavior.
- Added `entrypoint.ollama.sh` and wired `ollama-server` to run model sync before `ollama serve`.
- Added `make models-sync` to execute sync inside an `ollama-server` container (`--sync-only`).
- Moved llama.cpp `LLM_CONFIG` JSON files from `workspace/configs/` to `workspace/models/`.
- Added `workspace/models/models-config.yaml` with strict per-model `source_type` validation (`ollama` or `gguf`) and mixed-source rejection.

### Local Claude Playbook Refresh (May 15, 2026)

- Rewrote `CLAUDE_CODE_LOCAL.md` to align with repo workflows and naming:
  - Makefile-first lifecycle commands for Ollama,
  - `ollama-server` service naming,
  - environment layering guidance (`.env` -> compose -> container env).
- Replaced malformed Modelfile and benchmark snippets with runnable examples.
- Added safer benchmark guidance (timeouts, bounded prompts, error handling).
- Added a discoverability section in `README.md` that links to `CLAUDE_CODE_LOCAL.md`.
- Follow-up: clarified that Ollama `Modelfile` uses Dockerfile-like syntax and should be stored in `workspace/models`.
- Committed artifacts: `scripts/entrypoint.ollama.sh`, `scripts/entrypoint.llamacpp.sh`, `scripts/build_models.sh`, `scripts/aliases.sh` — all shell scripts consolidated under `scripts/`.

