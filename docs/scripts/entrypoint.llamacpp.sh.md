# entrypoint.llamacpp.sh

## Purpose

Entrypoint script for the llama.cpp Python server container. Starts both Jupyter Lab and the llama-cpp-python server.

## Usage

```bash
# In container (automatically used)
/app/scripts/entrypoint.llamacpp.sh
```

## Description

This script:
1. Sets `LLM_CONFIG` environment variable (default: config.json)
2. Starts Jupyter Lab in background (no browser, allow root)
3. Starts the llama-cpp-python server with the config file

## Environment Variables

- `LLM_CONFIG` - Config file name (default: config.json)
- `JUPYTER_LAB_CMD` - Jupyter command to run (default: jupyter-lab --no-browser --allow-root)

## See Also

- [entrypoint.ollama.sh](entrypoint.ollama.sh.md) - Ollama entrypoint
- [../services/llama-cpp.md](../services/llama-cpp.md) - Llama.cpp service documentation
