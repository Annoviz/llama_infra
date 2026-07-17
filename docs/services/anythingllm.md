# AnythingLLM service

## Project
- URL: `https://github.com/Mintplex-Labs/anything-llm`
- Description: Full-stack LLM workspace for chat, agents, documents, and retrieval workflows.

## Compose
- File: `compose/main/20-anythingllm.yml`
- Service name: `anythingllm`
- Image: `mintplexlabs/anythingllm:${ANYTHINGLLM_VERSION:-1.15.0}`

## Ports
- `3001:3001`

## Dependencies
- Depends on `ollama-server`.

## Make targets
- `make up-anythingllm`
- `make logs-anythingllm`
- `make restart-anythingllm`

## Notes
- Starts with Ollama integration environment pre-wired in compose.
