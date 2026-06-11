#!/usr/bin/env bash
# Local Claude Code + Ollama shell aliases
# Usage: source scripts/aliases.sh   (or add to ~/.bashrc)

export CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072

# Configure Claude for cloud routing (team / work profile)
claude-set-work() {
  unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_DEFAULT_HAIKU_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL
  export CLAUDE_CONFIG_DIR=~/.claude
}

# Configure Claude for local Ollama routing
claude-set-local() {
  export ANTHROPIC_BASE_URL=http://localhost:11434
  export ANTHROPIC_AUTH_TOKEN=ollama
  export ANTHROPIC_DEFAULT_HAIKU_MODEL=fast-coder
  export ANTHROPIC_DEFAULT_SONNET_MODEL=coder
  export ANTHROPIC_DEFAULT_OPUS_MODEL=planner
  export CLAUDE_CONFIG_DIR=~/.claude-local
}

# Restore standard cloud routing (team / work profile)
alias claude-work='claude-set-work; claude'

# Convenience alias for local planner model
alias claude-local='claude-set-local; claude'

