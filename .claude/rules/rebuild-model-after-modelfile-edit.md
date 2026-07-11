---
name: rebuild-model-after-modelfile-edit
description: Always rebuild Ollama model after Modelfile edits before testing
trigger: modelfile, ollama create, fast-coder, planner, mmproj
---

# Rule: Rebuild Model After Modelfile Edit

When a `.Modelfile` under `workspace/models/` is edited, **always rebuild the model in Ollama** before running any tests or vision checks.

## Why

Ollama caches loaded models in VRAM. Editing a Modelfile on disk does NOT change what's running — the old blob stays loaded until explicitly recreated. This caused wasted debugging time chasing a stale Q4_K_M blob when UD-Q4_K_XL was intended.

## How to Apply

After editing `workspace/models/<NAME>.Modelfile`:

```bash
# Rebuild inside Ollama container:
docker exec ollama-server ollama create <name> -f /models/<NAME>.Modelfile

# Or via Makefile target (once added):
make model-rebuild NAME=<name>
```

Then verify with the vision test or a generate call before proceeding.
