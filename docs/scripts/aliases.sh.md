# aliases.sh

## Purpose

Shell aliases and convenience functions for configuring Claude to use either cloud-based or local Ollama routing.

## Usage

```bash
source scripts/aliases.sh
```

Or add to `~/.bashrc` for persistent availability.

## Functions

### claude-set-work()

Configure Claude for cloud routing (team/work profile). Clears local environment variables and sets the standard Claude config directory.

### claude-set-local()

Configure Claude for local Ollama routing. Sets:
- `ANTHROPIC_BASE_URL=http://localhost:11434`
- `ANTHROPIC_AUTH_TOKEN=ollama`
- `CLAUDE_CODE_HAIKU_MODEL=fast-coder` (Claude Code model selection)
- `CLAUDE_CODE_SONNET_MODEL=fast-coder` (Claude Code model selection)
- `CLAUDE_CODE_OPUS_MODEL=planner` (Claude Code model selection)
- `CLAUDE_CODE_SUBAGENT_MODEL=fast-coder` (subagents only)
- `CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072`
- `CLAUDE_CONFIG_DIR=~/.claude-local`

**Note:** The legacy `ANTHROPIC_DEFAULT_*_MODEL` variables are kept for compatibility but are ignored by Claude Code. Use `CLAUDE_CODE_*_MODEL` instead.

## Aliases

### claude-work

Runs `claude-set-work` then launches Claude with cloud routing.

### claude-local

Runs `claude-set-local` then launches Claude with local Ollama routing.

## Examples

```bash
# Load aliases
source scripts/aliases.sh

# Use local Ollama
claude-local

# Use cloud Claude
claude-work
```

## See Also

- [entrypoint.ollama.sh](entrypoint.ollama.sh.md) - Ollama entrypoint with model picker
- [../operations.md](../operations.md) - Claude setup guide
