# AGENTS.md - llama_infra

Two independent Docker stacks: **main** (Ollama + AnythingLLM + Open WebUI) and **llama.cpp** (native C++ server). Mutually exclusive with vLLM stack. Do not assume cross-stack compatibility.

## Must-know rules

1. **Use `make` over raw `docker compose`** — every service has a target (`up-main`, `logs-ollama`, `ps-all`). Run `make help` to list them all.
2. **Config-first**: model/server values belong in JSON configs and `.env` variables, never hardcoded.
3. **Env layering**: `.env` → compose env → container env. Never override what's already in `.env`.
4. **`workspace/requirements.txt` is frozen** — report-only, never edit directly.
5. **Never delete `./models` or `MODELS` data** — treat as immutable user data.

## Architecture

| Stack | Compose files | Key services | Notes |
|---|---|---|---|
| Main | `compose/main/*.yml` | Ollama, AnythingLLM, Open WebUI, FalkorDB, MCPs | Default stack |
| llama.cpp | `compose/llama/*.yml` + `docker-compose.llama.cpp.yml` | llamacpp-server, router, Python server | GPU-native inference |
| vLLM | `compose/vllm/*.yml` | LiteLLM gateway + 3 engines | Drop-in Ollama replacement on port 11434; mutually exclusive with main |

Model configs live in `workspace/models/*.json`. All model paths use `/models/...` mount convention (host path from `MODELS` in `.env`).

## Developer commands

```bash
# Stack lifecycle
make up-main          # Start main stack
make down-all         # Stop everything
make ps-all           # Status all stacks
make logs-ollama      # Follow Ollama logs

# Validation (run before commits that touch infra)
make config-all       # Render all compose configs
make verify-agent-routing  # Validate AGENTS.md subagent structure

# Version updates (managed by tools/update_manager.py)
make updates-check    # Discover outdated packages/images
make updates-suggest  # Generate proposal JSON
make updates-apply    # Apply safe updates

# Model management
make models-sync        # Sync models from models-config.yaml inside ollama-server
make download-vllm-models  # Pre-download HF models to ${MODELS}/vllm/

# Benchmarking
make perf-test [ARGS='--model foo --iterations 5']  # Raw benchmark runner
make perf-test-planner    # → benchmarks/planner/results.json
make perf-test-coder      # → benchmarks/coder/results.json
make perf-test-fast-coder # Two passes for consistency check
python3 scripts/model_regression.py --reference ref.json current.json  # Compare runs

# Model config verification
cat workspace/models/*.json   # Inspect model configs
# Required fields: model_alias, chat_format, model path (/models/...)
```

## Model config conventions (`workspace/models/*.json`)

Required schema fields per model entry: `model`, `model_alias`, `chat_format`. Optional but common: `clip_model_path` (vision/mmproj), `n_gpu_layers`, `offload_kqv`, `n_ctx`.

Path convention: always `/models/...` relative to container mount. Host path is set via `MODELS` env var (default: `/mnt/data/workspaces/llama_infra/models`).

## Subagent routing

When the user requests a subagent by name, route directly. Otherwise, infer from keywords and pick the highest-scoring match (threshold ≥ 5).

| Subagent | Keywords | Score |
|---|---|---|
| `docker-ops-agent` | `make up-*`, `logs-*`, `ps-*`, GPU, compose, nvidia-smi | 5 |
| `model-config-agent` | LLM_CONFIG, GGUF, mmproj, model_alias, chat_format, workspace/models | 5 |
| `update-manager-agent` | updates-check/suggest/apply, requirements-dev, LLAMA_CPP_VERSION, update_manager.py | 5 |
| `reviewer-agent` | review, code review, audit, risk, regression, missing tests | 5 |
| `commit-agent` | commit, push, stage all, prepare commit | 5 |
| `docs-sync-agent` | README, CHANGELOG, document, sync docs | 4 |
| `coding-agent` | implement, feature, refactor, fix bug, patch | 3 |

Tie-break: exact file matches > generic words. If best score < 5, ask one clarification question.

Clarification question example: "Help with deployment and docs" → ask whether to prioritize deployment triage (`docker-ops-agent`) or docs sync (`docs-sync-agent`).

Negative Cases (should not route these):
- "Only review this patch; do not modify files" → use `reviewer-agent`, not `coding-agent`
- "Please implement this fix directly" → use `coding-agent`, not `reviewer-agent`
- "Restart services and inspect logs" → use `docker-ops-agent`, not `docs-sync-agent`

## Commit conventions

Prefix with type: `model:` (modelfile/model config), `infra:` (Docker/compose/Makefile), `chore:` (deps/version bumps), `docs:` (README/CHANGELOG), `test:` (tests), `fix:` (bug fixes).

Format: `<type>: <short summary>\n\n<detail if needed>\n\nCo-Authored-By: Claude <noreply@anthropic.com>`

## Gotchas

| Trap | Why it matters |
|---|---|
| New Makefile target not in `.PHONY` | Target only fires once (make thinks file exists) |
| `workspace/requirements.txt` modified by automation | Frozen snapshot — flag as error |
| Modelfile edited but model not rebuilt via compose | Vision/mmproj changes silently ignored at runtime |
| Hardcoded secrets in compose files | Should use `${VAR}` from `.env` |
| vLLM + main both up on port 11434 | Port collision — stacks are mutually exclusive |
| `docker-compose.llama.cpp.yml` doesn't exist | llama.cpp stack uses individual files under `compose/llama/*.yml` |

## Doc sources of truth

- Version pins: [docs/versioning.md](docs/versioning.md)
- Service docs: [docs/services/](docs/services/)
- Operations guide: [docs/operations.md](docs/operations.md)
- Update manager workflow: `tools/update_manager.py` + tests in `tests/test_update_manager.py`

## Subagent definitions

### docker-ops-agent
Handle Docker stack lifecycle, service status/logs/GPU checks. Owns Makefile targets for main and llama.cpp stacks (`make config-*`, `make ps-*`, `make logs-*`). Do not edit model JSON internals or manage version bumps (update-manager-agent).

### model-config-agent
Model configuration in `workspace/models/*.json`. Owns `/models/...` path conventions, `model_alias`, `chat_format`, multimodal `clip_model_path`. Validate schema fields and suggest minimal config changes.

### update-manager-agent
Version bump automation via `tools/update_manager.py`. Owns `make updates-check/suggest/apply`, managed version defaults in compose/Dockerfile files. Keep `workspace/requirements.txt` frozen. Do not own model tuning or service incident triage.

### reviewer-agent
Review code/config changes for correctness, regressions, risk, and missing tests. Report findings ordered by severity with file references. Route implementation follow-ups to coding-agent.

### commit-agent
Git staging, committing (conventional commits), and pushing after validation is complete. Do not bypass checks or rewrite/force-push without explicit request.

### docs-sync-agent
Keep README.md and CHANGELOG.md aligned with implementation changes. Update workflow examples to match current Makefile targets. If docs reveal an implementation inconsistency, hand off to owning subagent.

### coding-agent
Implement features, refactors, bug fixes in tracked source files with matching tests. Do not own stack operations (docker-ops-agent) or version bumps (update-manager-agent). Route doc-only work to docs-sync-agent.

## Memory system

Claude Code session memories are stored in the `llama_infra_memory` FalkorDB graph (MCP server at `http://localhost:3005`). File-based memory (`~/.claude/projects/*/memory/`) is a fallback.

Query examples:
```cypher
MATCH (m:Memory) RETURN m.name, m.type, m.description
MATCH (m:Memory)-[:RELATED_TO]->(t:Topic) RETURN m, t
```

## Tests

Run with conda env `llama_infra`:
```bash
conda run -n llama_infra python3 -m pytest -v tests/
conda run -n llama_infra python3 -m pytest --cov=. --cov-report=term-missing tests/
```

55 tests, ~63% coverage. See `tests/conftest.py` for shared fixtures and [docs/operations.md](docs/operations.md) for test writing conventions.
