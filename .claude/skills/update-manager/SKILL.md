---
name: update-manager
description: Check, suggest and apply Docker image and Python package version updates
---

# Skill: Update Manager

Manage Docker image and Python package versions in the llama_infra project using `tools/update_manager.py`.

## Commands

### Check Available Updates
```
/skill update-manager check
```
Runs `make updates-check` to discover available Docker tag and PyPI version updates.
**Always review the update report before applying.**

### Apply Updates (Interactive - Recommended)
```
/skill update-manager apply
```
Runs `make updates-apply` to show diffs and prompt for confirmation before applying updates.
**Each tool update requires your explicit approval.**

### Apply Updates (Non-interactive)
```
/skill update-manager apply --yes
```
Runs `make updates-apply --yes` to apply updates without interactive confirmation.
**Use with caution - no prompts will be shown.**

## Important: Manual Approval Required

**For each tool update, you must explicitly approve the changes:**
1. Run `/skill update-manager check` to see available updates
2. Run `/skill update-manager apply` (without `--yes`)
3. Review the proposed diffs
4. Answer `y` to confirm or `n` to cancel

This ensures you have full visibility and control over all version bumps.

## Docker Images Managed

The update manager currently checks these Docker images:

| Service | Image | Version Variable |
|---------|-------|------------------|
| Ollama | `ollama/ollama` | `OLLAMA_VERSION` |
| AnythingLLM | `mintplexlabs/anythingllm` | `ANYTHINGLLM_VERSION` |
| Open WebUI | `ghcr.io/open-webui/open-webui` | `OW_VERSION` |
| FalkorDB | `falkordb/falkordb` | `FALKORDB_VERSION` |
| FalkorDB MCP | `falkordb/mcpserver` | `FALKORDB_MCP_VERSION` |
| Unsloth | `unsloth/unsloth` | `UNSLOTH_VERSION` |
| Llama.cpp | `ghcr.io/ggml-org/llama.cpp` | `IMAGE` (for full-cuda-b tags) |

To add more images, extend `discover_docker_updates()` in `tools/update_manager.py`.

## Python Packages Managed

The update manager also checks `requirements-dev.txt` for PyPI package updates including:
- `llama-cpp-python[server]`
- `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`, `pytest-xdist`
- `black`, `ruff`, `pre-commit`
- And more...

## Examples

- "Check for available Docker image updates"
- "Apply all available version bumps"
- "Update Docker tags to latest"

## Workflow Example

```
# 1. Check what's available
make updates-check

# 2. Apply with manual approval
make updates-apply

# Or use the skill
/skill update-manager apply
```

**Remember:** Each tool update requires your explicit approval via interactive prompt.
