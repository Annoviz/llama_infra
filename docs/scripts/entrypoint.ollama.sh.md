# entrypoint.ollama.sh

## Purpose

Entrypoint script for the Ollama container. Handles model synchronization before starting the Ollama server.

## Usage

```bash
# In container (automatically used)
/app/scripts/entrypoint.ollama.sh

# Sync only mode
/app/scripts/entrypoint.ollama.sh --sync-only

# Validate only mode
/app/scripts/entrypoint.ollama.sh --validate-only
```

## Description

This script:
1. Reads model definitions from `models-config.yaml`
2. Pulls Ollama models or downloads GGUF files as specified
3. Starts the Ollama server (unless in sync/validate mode)

## Modes

- **serve** (default) - Sync models then start Ollama server
- **sync** - Only pull/download models, then exit
- **validate** - Only validate configuration, no downloads

## Environment Variables

- `MODELS_CONFIG` - Path to models config file (default: /app/workspace/models/models-config.yaml)
- `OLLAMA_MODELS` - Models directory (default: /models)
- `MODELS_SYNC_DRY_RUN` - If 1, show what would be pulled without pulling

## See Also

- [../services/ollama.md](../services/ollama.md) - Ollama service documentation
- [../../workspace/models/models-config.yaml](../../workspace/models/models-config.yaml) - Model configuration
