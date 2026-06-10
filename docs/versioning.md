# Version maintenance checklist

This document is the single source of truth for updating pinned container image versions in this repository.

## Current pinned defaults

Main stack (compose/main):

- Ollama: ollama/ollama:${OLLAMA_VERSION:-0.30.6}
- AnythingLLM: mintplexlabs/anythingllm:${ANYTHINGLLM_VERSION:-1.12.1}
- Open WebUI: ghcr.io/open-webui/open-webui:${OW_VERSION:-v0.8.11}
- FalkorDB: falkordb/falkordb:${FALKORDB_VERSION:-v4.18.9}
- FalkorDB MCP: falkordb/mcpserver:${FALKORDB_MCP_VERSION:-1.2.2}
- Unsloth: unsloth/unsloth:${UNSLOTH_VERSION:-2026.5.9-pt2.10.0-vllm-0.16.0-cu12.8-studio-release-v0.1.43-beta-2026-MAY-31}

llama.cpp stack:

- llama.cpp server image: ${IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda-b5350}
- llama.cpp Python base image: ${BASE_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda-b5350}
- llama-cpp-python app tag: ${LLAMA_CPP_VERSION:-0.3.23}

## Where to edit pins

- compose/main/10-ollama.yml
- compose/main/20-anythingllm.yml
- compose/main/30-open-webui.yml
- compose/main/40-falkordb.yml
- compose/main/50-falkordb-mcp.yml
- compose/main/60-unsloth.yml
- docker-compose.llama.cpp.yml
- compose/llama/Dockerfile.llamacpp-server-python

## Safe update workflow

1. Choose one service to update at a time.
2. Find candidate tag(s) on upstream registry release pages.
3. Validate candidate tag without editing files by overriding env vars in Make commands.
4. If candidate is healthy, update pinned default in compose file(s).
5. Update README defaults and CHANGELOG entry.
6. Re-run config and startup checks.

## Override validation commands

Use env overrides to test a candidate version before pinning.

Ollama:

```bash
OLLAMA_VERSION=<new_tag> make config-main
OLLAMA_VERSION=<new_tag> make pull-main
```

AnythingLLM:

```bash
ANYTHINGLLM_VERSION=<new_tag> make config-main
ANYTHINGLLM_VERSION=<new_tag> make pull-main
```

Open WebUI:

```bash
OW_VERSION=<new_tag> make config-main
OW_VERSION=<new_tag> make pull-main
```

FalkorDB:

```bash
FALKORDB_VERSION=<new_tag> make config-falkor
FALKORDB_VERSION=<new_tag> make pull-falkor
```

FalkorDB MCP:

```bash
FALKORDB_MCP_VERSION=<new_tag> make config-falkor
FALKORDB_MCP_VERSION=<new_tag> make pull-falkor
```

Unsloth:

```bash
UNSLOTH_VERSION=<new_tag> make config-unsloth
UNSLOTH_VERSION=<new_tag> make pull-unsloth
UNSLOTH_VERSION=<new_tag> make up-unsloth
make logs-unsloth
```

llama.cpp server image:

```bash
IMAGE=<new_tag> make config-llama
IMAGE=<new_tag> make pull-llama
```

llama.cpp Python image version:

```bash
LLAMA_CPP_VERSION=<new_tag> make build-llamacpp-py
LLAMA_CPP_VERSION=<new_tag> make up-llamacpp-py
make logs-llamacpp-py
```

llama.cpp base image:

```bash
BASE_IMAGE=<new_tag> make build-llamacpp-py
```

## Final verification checklist

Run after changing pinned defaults:

```bash
make config-all
make pull-all
make ps-all
```

Then do service-specific smoke checks:

- make logs-ollama
- make logs-anythingllm
- make logs-open-webui
- make logs-falkordb
- make logs-falkordb-mcp
- make logs-unsloth
- make logs-llamacpp
- make logs-llamacpp-py

## Documentation and changelog policy

- Always update README.md when any default pin changes.
- Always add a dated section in CHANGELOG.md with:
  - Added/Changed (as applicable)
  - Old value -> new value
  - Validation commands run

## Notes

- Keep UNSLOTH service optional: do not change make up-main behavior.
- Prefer specific tags over latest for reproducibility.
- workspace/requirements.txt is frozen and should not be edited by automation.

## Last verified

- Date: 2026-06-10
- All pinned defaults validated via `make config-all` and `make pull-all`.
