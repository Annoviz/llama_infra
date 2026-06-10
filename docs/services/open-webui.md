# Open WebUI service

## Project
- URL: `https://github.com/open-webui/open-webui`
- Description: Self-hosted web interface for interacting with local and remote LLM backends.

## Compose
- File: `compose/main/30-open-webui.yml`
- Service name: `open-webui`
- Image: `ghcr.io/open-webui/open-webui:${OW_VERSION:-v0.8.11}`

## Ports
- `3002:8080`

## Dependencies
- Depends on `ollama-server`.

## Make targets
- `make up-open-webui`
- `make logs-open-webui`
- `make restart-open-webui`

## Notes
- Configured to use Ollama endpoint on the shared main network.
