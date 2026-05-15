#!/usr/bin/env bash
# Local Claude Code + Ollama shell aliases
# Usage: source scripts/aliases.sh   (or add to ~/.bashrc)

# Route Claude Code to local Ollama planner model (no cloud account tracing)
alias planner='export ANTHROPIC_BASE_URL=http://localhost:11434/v1; export ANTHROPIC_AUTH_TOKEN=ollama; claude --model ollama/planner'

# Route Claude Code to local Ollama coder model
alias coder='export ANTHROPIC_BASE_URL=http://localhost:11434/v1; export ANTHROPIC_AUTH_TOKEN=ollama; claude --model ollama/coder'

# Restore standard cloud routing (team / work profile)
alias claude-work='unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN; CLAUDE_CONFIG_DIR=~/.claude-work claude'

# Convenience alias for local planner model (same as 'planner' above, the switch to coder can be done interactively in the CLI)
alias claude-local='export ANTHROPIC_BASE_URL=http://localhost:11434/v1; export ANTHROPIC_AUTH_TOKEN=ollama; ; CLAUDE_CONFIG_DIR=~/.claude-local; claude --model ollama/planner'

