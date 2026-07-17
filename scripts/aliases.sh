#!/usr/bin/env bash
# Local Claude Code + Ollama shell aliases
# Usage: source scripts/aliases.sh   (or add to ~/.bashrc)



# Configure Claude for cloud routing (team / work profile)
claude-set-work() {
  unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN
  unset CLAUDE_CODE_HAIKU_MODEL CLAUDE_CODE_SONNET_MODEL CLAUDE_CODE_OPUS_MODEL
  unset CLAUDE_CODE_SUBAGENT_MODEL
  export CLAUDE_CONFIG_DIR=~/.claude
}

# Configure Claude for local Ollama routing
claude-set-local() {
  export ANTHROPIC_BASE_URL=http://localhost:11434
  export ANTHROPIC_AUTH_TOKEN=ollama
  # Legacy variable (kept for compatibility, but Claude Code ignores it)
  export ANTHROPIC_MODEL=planner
  export ANTHROPIC_DEFAULT_HAIKU_MODEL=fast-coder
  export ANTHROPIC_DEFAULT_SONNET_MODEL=planner
  export ANTHROPIC_DEFAULT_OPUS_MODEL=coder
  export ANTHROPIC_DEFAULT_FABLE_MODEL=coder
  export CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072
  export CLAUDE_CODE_ATTRIBUTION_HEADER=0
  export CLAUDE_CODE_SUBAGENT_MODEL=fast-coder
  export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
  export DISABLE_TELEMETRY=1
  export CLAUDE_CONFIG_DIR=~/.claude-local
  echo "Configured Claude for local Ollama routing (team / work profile)"
}

# Restore standard cloud routing (team / work profile)
alias claude-work='claude-set-work; claude'

# Convenience alias for local planner model
alias claude-local='claude-set-local; claude'

