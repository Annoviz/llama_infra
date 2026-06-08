#!/usr/bin/env bash
# Local Claude Code + Ollama shell aliases
# Usage: source scripts/aliases.sh   (or add to ~/.bashrc)

export CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072


# Route Claude Code to local Ollama planner model (no cloud account tracing)
alias claude-local-planner='export ANTHROPIC_BASE_URL=http://localhost:11434; export ANTHROPIC_AUTH_TOKEN=ollama; export ANTHROPIC_DEFAULT_HAIKU_MODEL=fast-coder; export ANTHROPIC_DEFAULT_SONNET_MODEL=coder; export ANTHROPIC_DEFAULT_OPUS_MODEL=planner; export CLAUDE_CONFIG_DIR=~/.claude-local; claude --model planner'

# Route Claude Code to local Ollama coder model
alias claude-local-coder='export ANTHROPIC_BASE_URL=http://localhost:11434; export ANTHROPIC_AUTH_TOKEN=ollama; export ANTHROPIC_DEFAULT_HAIKU_MODEL=fast-coder; export ANTHROPIC_DEFAULT_SONNET_MODEL=coder; export ANTHROPIC_DEFAULT_OPUS_MODEL=planner; export CLAUDE_CONFIG_DIR=~/.claude-local; claude --model coder'

# Route Claude Code to local Ollama fast-coder model
alias claude-local-fast-coder='export ANTHROPIC_BASE_URL=http://localhost:11434; export ANTHROPIC_AUTH_TOKEN=ollama; export ANTHROPIC_DEFAULT_HAIKU_MODEL=fast-coder; export ANTHROPIC_DEFAULT_SONNET_MODEL=coder; export ANTHROPIC_DEFAULT_OPUS_MODEL=planner; export CLAUDE_CONFIG_DIR=~/.claude-local; export CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072; claude --model fast-coder'

# Restore standard cloud routing (team / work profile)
alias claude-work='unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_DEFAULT_HAIKU_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL; export CLAUDE_CONFIG_DIR=~/.claude-work; claude'

# Convenience alias for local planner model (same as planner alias)
alias claude-local='export ANTHROPIC_BASE_URL=http://localhost:11434; export ANTHROPIC_AUTH_TOKEN=ollama; export ANTHROPIC_DEFAULT_HAIKU_MODEL=fast-coder; export ANTHROPIC_DEFAULT_SONNET_MODEL=coder; export ANTHROPIC_DEFAULT_OPUS_MODEL=planner; export CLAUDE_CONFIG_DIR=~/.claude-local; claude'

# Interactive local model picker (reads model list from Ollama and launches Claude)
alias claude-local-picker='export ANTHROPIC_DEFAULT_HAIKU_MODEL=fast-coder; export ANTHROPIC_DEFAULT_SONNET_MODEL=coder; export ANTHROPIC_DEFAULT_OPUS_MODEL=planner; bash scripts/claude-local-picker.sh'
