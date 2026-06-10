# llama.cpp stack

## Project
- URL: `https://github.com/ggml-org/llama.cpp`
- Description: C/C++ inference stack for running GGUF models locally, with native and Python server options.

## Compose
- File: `docker-compose.llama.cpp.yml`
- Services:
  - `llamacpp-server`
  - `llamacpp-server-py`

## Images
- Native server: `${IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda-b5350}`
- Python server image: `${REGISTRY:-llamacpp-server-python}/llamacpp-server-py:${LLAMA_CPP_VERSION:-0.3.23}`
- Python build base image: `${BASE_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda-b5350}`

## Make targets
- `make up-llamacpp`
- `make build-llamacpp-py`
- `make up-llamacpp-py`
- `make up-llama`
- `make logs-llamacpp`
- `make logs-llamacpp-py`
- `make down-llama`

## Notes
- This stack is separate from the main compose stack.
- GPU checks: `make gpu-host` and `make gpu-smoke-llamacpp`.
