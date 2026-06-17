# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`llama_infra` is a local LLM infrastructure toolkit that runs Ollama, AnythingLLM, Open WebUI, and llama.cpp servers via Docker Compose. It also includes agent routing, model management, and a dependency update manager.

## Architecture

Two independent Docker stacks:

1. **Main stack** (`compose/main/*.yml`, assembled via `Makefile`): `ollama-server` + `anythingllm` + `open-webui` (+ optional FalkorDB MCP services)
2. **llama.cpp stack** (`docker-compose.llama.cpp.yml`): native C++ server + Python server

These stacks are intentionally separate; do not assume cross-stack compatibility.

Key directories:
- `workspace/models/` — Ollama Modelfiles, llama.cpp JSON configs, `models-config.yaml` (model sync contract)
- `workspace/requirements.txt` — frozen Python dependency snapshot (never edit directly)
- `tools/update_manager.py` — checks/applies Docker tag and Python package updates
- `tools/check_agent_docs.py` — validates `.github/agents/*.md` structure
- `.github/agents/` — Markdown subagent definitions for agent routing
- `scripts/` — shell scripts (entrypoints, aliases, model build helpers, benchmark runner)
- `tests/` — pytest suite with 55 tests and 63% coverage

## Key Files

- `AGENTS.md` — router rules, global rules, and subagent discovery convention
- `CLAUDE_CODE_LOCAL.md` — local Claude Code + Ollama setup playbook
- `CHANGELOG.md` — project changelog
- `.env` — environment overrides (models path, data dir, GPU ID, registry)
- `requirements-dev.txt` — editable dev dependency source
- `requirements-client.txt` — pinned client deps (frozen snapshot in `workspace/requirements.txt`)
- `tests/conftest.py` — shared pytest fixtures

## Common Commands

### Docker stacks
```bash
make up-main            # Start Ollama + AnythingLLM + Open WebUI
make up-ollama          # Start Ollama only
make up-llamacpp        # Start native llama.cpp server
make up-llamacpp-py     # Start Python llama-cpp server
make down-main          # Stop main stack
make down-llama         # Stop llama.cpp stack
make logs-ollama        # Follow Ollama logs
make ps-all             # Show containers in both stacks
```

### Model management
```bash
make models-sync        # Sync models inside ollama-server
```

### Code quality
```bash
make precommit-install  # Install pre-commit hooks
make precommit-run      # Run all hooks (ruff, black, yaml/json checks, agent docs)
make verify-agent-routing  # Validate agent docs + run unit tests
```

### Benchmarking
```bash
make perf-test ARGS="--model planner --iterations 5"   # Run performance tests (raw)

# Named targets — run benchmark + optional regression comparison:
make perf-test-planner          # → benchmarks/planner/results.json
make perf-test-coder            # → benchmarks/coder/results.json
make fast-coder                 # → benchmarks/fast-coder/results.json
make perf-test-fast-coder       # two passes for consistency check

# Regression comparison (when reg-results.json exists in output dir):
python3 scripts/model_regression.py --reference ref.json current.json  # Compare runs
```

### Update manager
```bash
make updates-check      # Check latest Docker tags and Python versions
make updates-suggest    # Write .update-manager-proposal.json
make updates-apply      # Interactive diff + apply
```

### Tests

```bash
# Run all tests (requires conda environment)
conda run -n llama_infra python3 -m pytest -v tests/

# Run with coverage
conda run -n llama_infra python3 -m pytest --cov=. --cov-report=term-missing tests/
```

See [docs/operations.md](docs/operations.md) for test structure and writing tests.

## Agent Routing

Subagents live in `.github/agents/*.md`. Routing rules (keyword scoring, tie-breaks, fallback) are in `AGENTS.md`.

| Agent | Purpose | Key triggers |
|---|---|---|
| `docker-ops-agent` | Docker stack lifecycle, logs, GPU checks | `make up-*`, `logs-`, `ps-*`, `gpu`, `compose` |
| `model-config-agent` | Model JSON configs, GGUF/mmproj wiring | `LLM_CONFIG`, `GGUF`, `mmproj`, `model_alias` |
| `update-manager-agent` | Docker tag and Python dependency updates | `updates-check`, `updates-apply`, `requirements-dev` |
| `docs-sync-agent` | README/CHANGELOG alignment | `README`, `CHANGELOG`, `sync`, `document` |
| `coding-agent` | Feature implementation, refactors, bug fixes | `implement`, `feature`, `refactor`, `fix bug` |
| `reviewer-agent` | Code review, regression risk, missing tests | `review`, `audit`, `risk`, `regression` |
| `commit-agent` | Git commit and push workflows | `commit`, `push`, `stage all` |

When routing rules or subagent docs change, run `make verify-agent-routing` before handoff.

## Memory System

Claude Code session memories are stored in the `llama_infra_memory` FalkorDB graph (MCP server at `http://localhost:3005`). File-based memory (`~/.claude/projects/*/memory/`) is a fallback.

To query memories:
```cypher
MATCH (m:Memory) RETURN m.name, m.type, m.description
MATCH (m:Memory)-[:RELATED_TO]->(t:Topic) RETURN m, t
```

## Development Notes

- Use `make` targets instead of raw `docker compose` commands when a target exists.
- Keep configuration in JSON configs and env vars, not hardcoded values.
- Preserve environment layering: `.env` -> compose env -> container env.
- `workspace/requirements.txt` is a frozen snapshot — report-only in automation.
- Never suggest deleting `./models` without explicit data-loss intent.

## Mode Constraints
- When the user asks to plan, or when the system is set to plan mode, you are STRICTLY PROHIBITED from modifying files or running edit tools.
- You must output your execution strategies strictly as text descriptions in the terminal console. Do not proceed to implementation until explicitly told "Go ahead".
