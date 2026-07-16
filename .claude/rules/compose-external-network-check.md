# Rule: Verify External Networks Before Compose Changes

When adding a new compose service that references an external network (e.g., `ollama-bridge`), verify the network exists before composing.

## Why

External networks are created by other stacks or manually — they don't auto-create when you add them to a compose file. A missing network causes immediate `docker compose config` failure and blocks deployment.

## How to Apply

After adding an external network reference:
```bash
docker network inspect <network-name> 2>&1 | head -3
# If it fails, create it or confirm the referencing stack creates it
```

For `ollama-bridge`, it's created by the vLLM stack — check that first.
