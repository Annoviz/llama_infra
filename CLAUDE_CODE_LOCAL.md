# Local Claude Code + Ollama Playbook (repo-aligned)

This guide is aligned with the current `llama_infra` repository workflow.
It assumes a Linux host with NVIDIA GPU support and Docker configured for GPUs.

## Scope and safety

- Main target stack: split compose files under `compose/main/` (prefer Make targets).
- Prefer Make targets when available (`make up-ollama`, `make logs-ollama`, etc.).
- Keep configuration layered: `.env` -> compose defaults -> container environment.
- Do not delete local model assets in `./models` unless you explicitly intend data loss.

## Phase 1 - Bring up Ollama with repo workflow

1. Review defaults in `compose/main/*.yml` and optional overrides in `.env`.
2. Start only Ollama first, then validate service and logs.

```bash
make up-ollama
make ps-main
make logs-ollama
```

3. Validate GPU visibility on host.

```bash
make gpu-host
```

4. Optional: run a container-level smoke check if needed.

```bash
docker compose --project-directory . \
    -f compose/main/00-networks-and-volumes.yml \
    -f compose/main/10-ollama.yml \
    exec -T ollama-server ollama --version
```

## Phase 2 - Build planner and coder model aliases

`Modelfile` uses Dockerfile-like syntax (`FROM`, `PARAMETER`, `SYSTEM`).
Store these files in the repo under `workspace/models`.

Create the Modelfile directory in your repo (run from the repo root):

```bash
mkdir -p workspace/models
```

Create `workspace/models/Planner.Modelfile`:

```dockerfile
FROM qwen3.6:35b
PARAMETER num_ctx 65536
PARAMETER temperature 0.1
PARAMETER keep_alive 24h

SYSTEM """
You are the planning agent.
Analyze architecture, dependencies, and risks.
Return structured implementation steps.
"""
```

Create `workspace/models/Coder.Modelfile`:

```dockerfile
FROM qwen3.6:27b
PARAMETER num_ctx 32768
PARAMETER temperature 0.3
PARAMETER keep_alive 24h

SYSTEM """
You are the coding agent.
Implement requested changes precisely and safely.
"""
```

Create and run `scripts/build_models.sh`:

```bash
cat > build_models.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# Set LLAMA_INFRA_DIR to the repo root if not already exported in your shell
LLAMA_INFRA_DIR="${LLAMA_INFRA_DIR:-$(cd "$(dirname "$0")" && pwd)}"

docker compose --project-directory "$LLAMA_INFRA_DIR" \
    -f "$LLAMA_INFRA_DIR/compose/main/00-networks-and-volumes.yml" \
    -f "$LLAMA_INFRA_DIR/compose/main/10-ollama.yml" \
  exec -T ollama-server ollama create planner -f - < "$LLAMA_INFRA_DIR/workspace/models/Planner.Modelfile"

docker compose --project-directory "$LLAMA_INFRA_DIR" \
    -f "$LLAMA_INFRA_DIR/compose/main/00-networks-and-volumes.yml" \
    -f "$LLAMA_INFRA_DIR/compose/main/10-ollama.yml" \
  exec -T ollama-server ollama create coder -f - < "$LLAMA_INFRA_DIR/workspace/models/Coder.Modelfile"

docker compose --project-directory "$LLAMA_INFRA_DIR" \
    -f "$LLAMA_INFRA_DIR/compose/main/00-networks-and-volumes.yml" \
    -f "$LLAMA_INFRA_DIR/compose/main/10-ollama.yml" \
  exec -T ollama-server ollama list
EOF

chmod +x build_models.sh
./build_models.sh
```

Notes:

- Model tags above are examples; validate availability for your Ollama registry.
- Keep model/runtime settings in env vars and compose config, not hardcoded app code.

## Phase 3 - Bash aliases for local routing

An example alias file is committed at `scripts/aliases.sh`.

**Option A — source per session (no permanent change):**

```bash
source scripts/aliases.sh
```

**Option B — persist in your shell profile:**

```bash
echo 'source /path/to/repo/scripts/aliases.sh' >> ~/.bashrc
source ~/.bashrc
```

The file defines three aliases:

| Alias | Effect |
|---|---|
| `planner` | Routes Claude Code to local `ollama/planner` model |
| `coder` | Routes Claude Code to local `ollama/coder` model |
| `claude-work` | Restores standard cloud routing (team/work profile) |

## Phase 4 - Validation and telemetry

In one terminal:

```bash
watch -n 0.5 nvidia-smi
```

In another terminal:

```bash
make logs-ollama
```

Then run:

```bash
planner
```

Inside your Claude session, switch model aliases as needed:

```text
/model ollama/coder
/model ollama/planner
```

## Phase 5 — Benchmarking & regression tracking

The repo ships two Python scripts for systematic model benchmarking with JSON output and regression comparison.

### Running benchmarks

`scripts/perf_test.py` measures TTFT, throughput, and duration per iteration via the Ollama `/api/chat` endpoint. It writes structured results to `output_dir/results.json`.

```bash
# Quick single-model run (3 iterations × 3 default prompts)
python3 scripts/perf_test.py planner --iterations 5 --output-dir ./benchmarks/planner

# Multi-model, custom prompt file
python3 scripts/perf_test.py \
    --models coder,planner \
    --prompts-file workspace/prompts.txt \
    --max-tokens 256 \
    --iterations 5 \
    --output-dir ./benchmarks/run-$(date +%Y%m%d)

# Table output (default), or JSON to stdout:
python3 scripts/perf_test.py coder --json
```

**Key options:** `--prompts-file`, `--max-tokens N`, `--iterations N`, `--timeout SECS`, `--base-url URL`.  
Each run gets a unique `run_id` (timestamp + random suffix) and the output directory contains:

- `results.json` — full structured data: per-iteration metrics, aggregates, raw response text, and the original prompt.

### Comparing against a reference (regression detection)

`scripts/model_regression.py` loads a previous `results.json` and compares performance + output consistency for every matched `(model, prompt)` combo.

```bash
# Compare latest run against an older baseline
python3 scripts/model_regression.py \
    --reference ./benchmarks/old-run/results.json \
    --output-dir ./regression-report

# Custom thresholds (5 % warn, 10 % critical)
python3 scripts/model_regression.py \
    --reference ./benchmarks/baseline/results.json \
    ./benchmarks/latest/results.json \
    --warn-threshold 5 --critical-threshold 10

# Pipe from stdin
cat results.json | python3 scripts/model_regression.py --reference ref_results.json
```

The regression report flags:
- **Performance regressions** — metric deltas on `tokens_per_sec`, `first_token_ms`, `total_duration_s` (warn ≥ 5 %, critical ≥ 10 %).
- **Output consistency** — whether all iterations produce identical text, and similarity of the first iteration vs reference.

Exit codes: `0` = no regressions, `1` = critical found, `2` = warnings only.

### Makefile shortcut

```bash
make perf-test ARGS="--model planner --iterations 5"   # runs perf_test.sh → perf_test.py
```

## Troubleshooting quick checks

```bash
make ps-main
make logs-ollama
docker compose --project-directory . \
    -f compose/main/00-networks-and-volumes.yml \
    -f compose/main/10-ollama.yml \
    exec -T ollama-server ollama list
```

If you hit VRAM pressure, tune model context and parallelism first (`OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`, and per-model context settings) before changing disk/model layout.

