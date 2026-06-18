# update_manager.py

## Purpose

Update manager for Docker image tags and Python package versions. Discovers available updates, suggests changes, and applies them interactively.

## Usage

```bash
python3 tools/update_manager.py <command> [options]
make updates-check
make updates-suggest
make updates-apply
```

## Commands

### check

List current and latest versions of managed dependencies.

### suggest

Same as check, plus writes a proposal JSON file (`.update-manager-proposal.json`).

### apply

Show diffs and apply after interactive confirmation.

Options:
- `--yes` - Skip prompt and apply changes

## Safety

- Updates only managed targets in compose/dockerfile/requirements-dev.txt
- Never edits `workspace/requirements.txt` (frozen snapshot)

## Managed Targets

### Docker Images
- ollama/ollama
- mintplexlabs/anythingllm
- ghcr.io/open-webui/open-webui
- falkordb/falkordb
- falkordb/mcpserver
- unsloth/unsloth
- ghcr.io/ggml-org/llama.cpp

### Python Packages
- llama-cpp-python[server]
- All packages in requirements-dev.txt

## Examples

```bash
# Check available updates
make updates-check

# Write proposal file
make updates-suggest

# Apply updates interactively
make updates-apply

# Apply updates non-interactively
make updates-apply --yes
```

## See Also

- [../operations.md](../operations.md) - Update workflow
- [../versioning.md](../versioning.md) - Version pinning guide
