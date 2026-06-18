# claude-local-picker.sh

## Purpose

Interactive Ollama model picker for Claude. Lists available local models and launches Claude with the selected model.

## Usage

```bash
scripts/claude-local-picker.sh
```

## Description

This script:
1. Queries Ollama for available models
2. Displays a numbered list of models
3. Prompts user to select a model
4. Configures Claude to use the selected model via Ollama

## Prerequisites

- `curl` - For querying Ollama API
- `python3` - For JSON parsing
- `claude` CLI - Available in PATH

## Examples

```bash
# Launch Claude with a local model
scripts/claude-local-picker.sh
```

## Environment Variables

- `OLLAMA_BASE_URL` - Ollama base URL (default: http://localhost:11434)
- `ANTHROPIC_BASE_URL_LOCAL` - Claude API URL (default: $OLLAMA_BASE_URL/v1)
- `ANTHROPIC_AUTH_TOKEN_LOCAL` - Auth token (default: ollama)
- `CLAUDE_CONFIG_DIR_LOCAL` - Config directory (default: $HOME/.claude-local)

## See Also

- [aliases.sh](aliases.sh.md) - Shell aliases for Claude configuration
- [entrypoint.ollama.sh](entrypoint.ollama.sh.md) - Ollama entrypoint with model sync
