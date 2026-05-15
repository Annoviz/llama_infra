# Update Manager Tool

`tools/update_manager.py` checks for newer Docker image tags and Python package versions, proposes changes, and applies updates only after confirmation.

## Managed targets

- Docker defaults in `docker-compose.yml`
  - `OLLAMA_VERSION`
  - `ANYTHINGLLM_VERSION`
  - `OW_VERSION`
- Docker defaults in `docker-compose.llama.cpp.yml`
  - `IMAGE` (`ghcr.io/ggml-org/llama.cpp:full-cuda-b*`)
  - `BASE_IMAGE`
  - `LLAMA_CPP_VERSION`
- Dockerfile defaults in `Dockerfile.llamacpp-server-python`
  - `ARG BASE_IMAGE`
  - `ARG LLAMA_CPP_VERSION`
- Python package constraints in `requirements-dev.txt`
  - Applies updates for `==` and `>=` constraints
  - Reports unpinned packages as info only

`workspace/requirements.txt` is treated as frozen and never edited.

## Usage

```bash
python3 tools/update_manager.py check
python3 tools/update_manager.py suggest
python3 tools/update_manager.py apply
```

`apply` is interactive and prompts:

```text
Apply these updates? [y/N]:
```

If you need non-interactive behavior for automation:

```bash
python3 tools/update_manager.py apply --yes
```
