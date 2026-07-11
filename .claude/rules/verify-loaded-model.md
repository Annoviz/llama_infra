---
name: verify-loaded-model
description: Verify which model Ollama actually loaded before assuming the right one is running
trigger: nvidia-smi, VRAM, wrong model, ollama tags, performance test
---

# Rule: Verify Loaded Model Before Testing

Before benchmarking or testing a model, verify that Ollama is actually serving the expected blob.

## Why

`/model fast-coder` in Claude Code sets the session model name, but doesn't guarantee Ollama loaded the right file. The old planner (~24 GB VRAM) was sitting in memory when we thought fast-coder (~3.4 GB) was active. `nvidia-smi` VRAM footprint is a quick sanity check.

## How to Apply

Quick verification methods:

```bash
# Check VRAM usage against expected model size:
nvidia-smi | grep MiB

# List models and sizes in Ollama:
curl -s http://localhost:11434/api/tags | python3 -c "
import sys, json
models = json.load(sys.stdin)['models']
for m in models:
    print(f\"{m['name']:50s} {m.get('size', '?'):>12}\")"

# Check what a specific model resolves to:
curl -s http://localhost:11434/api/show -d '{"name": "fast-coder"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('model','N/A')[:80])"
```

If VRAM doesn't match the expected model size, rebuild with `ollama create`.
