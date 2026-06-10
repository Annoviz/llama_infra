# Ollama service

## Project
- URL: `https://github.com/ollama/ollama`
- Description: Local LLM runtime and model manager that serves chat and completion APIs.

## Compose
- File: `compose/main/10-ollama.yml`
- Service name: `ollama-server`
- Image: `ollama/ollama:${OLLAMA_VERSION:-0.30.6}`

## Ports
- `11434:11434`

## Storage and mounts
- `${MODELS:-./models}:/models`
- `./workspace:/app/workspace`

## Make targets
- `make up-ollama`
- `make logs-ollama`
- `make restart-ollama`

## Notes
- GPU reservation is configured via Compose device capabilities.
- Use `make models-sync` to run model sync inside the container.
