# Operations guide

This document contains day-to-day operational workflows that were moved out of the top-level README.

## Client setup

```bash
# install mini conda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod +x Miniconda3-latest-Linux-x86_64.sh
./Miniconda3-latest-Linux-x86_64.sh

# create a new conda environment
conda create -n llama_infra python=3.10

# activate the conda environment
conda activate llama_infra

# install the client requirements
pip install -r requirements-client.txt

# run the client examples with jupyter: workspace/ollama_examples.ipynb
jupyter notebook
```

## Extra workflows

```bash
# Run the lamma.cpp server - WIP
make up-llamacpp

# Sync models inside the ollama-server container
make models-sync

# Download the models - Qwen2.5-VL-7B-Instruct (Not supported by the server yet)
mkdir -p models/Qwen2.5-VL-7B-Instruct
cd models/Qwen2.5-VL-7B-Instruct
wget https://huggingface.co/IAILabs/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/README.md
wget https://huggingface.co/IAILabs/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/Qwen2.5-VL-7B-Instruct-Q4_0.gguf
wget https://huggingface.co/IAILabs/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/mmproj-Qwen2.5-VL-7B-Instruct-F32.gguf
cd ../..

# Build the python server
make build-llamacpp-py

# Run the python server
make up-llamacpp-py
```

## Local Claude Code playbook

- Repo-aligned setup guide: CLAUDE_CODE_LOCAL.md
- Uses Makefile-first commands for Ollama lifecycle (make up-ollama, make logs-ollama, make ps-main)
- Covers model alias creation (planner, coder), shell routing aliases, and local benchmarking

## Model config locations

- Llama.cpp JSON server configs: workspace/models/*.json
- Model sync contract: workspace/models/models-config.yaml
- LLM_CONFIG is resolved as /app/workspace/models/${LLM_CONFIG} in scripts/entrypoint.llamacpp.sh
- Ollama startup and sync entrypoint: scripts/entrypoint.ollama.sh

## Update manager

- Update workflow reference: tools/README.md
- Version pinning and upgrade checklist: docs/versioning.md
- Editable dependency source: requirements-dev.txt
- Frozen snapshot (report-only): workspace/requirements.txt

### Major update process (major/minor jumps)

Routine patch bumps go through `make updates-check` → `make updates-apply` and the
standard verification below. **Major** updates (a new major version, or a jump that
skips minor releases, e.g. vLLM 0.26 → 0.28, huggingface_hub 0.35 → 1.29) follow
this extended process: fix what breaks, roll back only what cannot be fixed.

#### 1. Classify the change set

Run `make updates-check` and sort every `[UPDATE]` line by risk tier:

| Tier | Example | Default action |
|------|---------|----------------|
| Patch | falkordb v4.20.1 → v4.20.4, ruff 0.16.1 → 0.16.5 | Apply |
| Minor | ollama 0.32.6 → 0.33.2, anythingllm 1.15.0 → 1.16.1 | Apply |
| Major / multi-minor jump | huggingface_hub 0.35.0 → 1.29.0, vLLM v0.26.0 → v0.28.0 | Apply only after explicit user approval; verify per steps 3–4 |

For each major item, note *where* the version lands: `VERSIONS.env` (compose
`${VAR}` references), a Dockerfile `ARG`, or `requirements-dev.txt`. The update
manager writes all of these in one pass — review the printed diff before confirming.

#### 2. Inspect what the new base ships (before building)

For any pip pin that is installed *on top of* a base image, first check which
version the new base already contains — a large gap between the pin and the base's
own copy is the usual breakage source:

```bash
# e.g. before bumping HUGGINGFACE_HUB_VERSION for vLLM
docker run --rm --entrypoint python3 vllm/vllm-openai:<new-tag> \
  -c "import huggingface_hub; print(huggingface_hub.__version__)"
```

If the base ships a nearby version (e.g. base has 1.28.0 and we pin 1.29.0), risk
is low. If the base is on a different major line than our pin, expect API friction.

#### 3. Apply + config verification

```bash
make updates-apply          # review diff, confirm
make config-all             # all compose files must render
conda run -n llama_infra python3 -m pytest -q tests/   # full suite green
```

Note: the update manager's open-webui name mapping has historically skipped
`OW_VERSION` in `VERSIONS.env` even when it reports the bump — after every apply,
spot-check `git diff VERSIONS.env` against the reported list and fix any gap
manually.

#### 4. Per-stack verification matrix

| Stack | Rebuild needed? | Verification steps |
|-------|-----------------|--------------------|
| Main (ollama, anythingllm, open-webui, falkordb, unsloth) | No — image pull only | `make config-all`, `make pull-main` when ready; restart services on next `make up-main` |
| llama.cpp python server (`Dockerfile.llamacpp-server-python`) | Yes — `make build-llamacpp-py` | Build succeeds (it compiles `llama-cpp-python[server]` for CUDA); `make ps-llama` healthy after restart |
| vLLM stack (`Dockerfile.vllm`) | Yes — see detailed flow below | `make smoke-vllm`, `make build-vllm`, runtime checks in the built image |

**vLLM detailed flow (major bumps):**

```bash
# 4a. validate compose + pull new base images (also proves tags exist upstream)
make smoke-vllm

# 4b. build all 3 engine images (runs the pip pin step)
make build-vllm

# 4c. runtime compatibility check INSIDE the built image:
docker run --rm --entrypoint python3 ${REGISTRY}/vllm:${VLLM_VERSION} \
  -c "import huggingface_hub as h, vllm; print(h.__version__, vllm.__version__)"
docker run --rm --entrypoint vllm ${REGISTRY}/vllm:${VLLM_VERSION} serve --help >/dev/null && echo OK

# 4d. exercise the entrypoint's cache logic under BOTH conditions:
#     - fresh/empty cache dir (must NOT crash; must report 'not cached')
#     - real host cache ${MODELS}/vllm (must find the pre-downloaded repos,
#       i.e. no redundant re-download)
docker run --rm -v /mnt/data/workspaces/llama_infra/models/vllm:/root/.cache/huggingface \
  -e HF_HOME=/root/.cache/huggingface --entrypoint python3 ${REGISTRY}/vllm:${VLLM_VERSION} \
  -c "from huggingface_hub import scan_cache_dir; print([r.repo_id for r in scan_cache_dir().repos])"

# 4e. optional full engine start (needs GPU headroom — skip if other stacks are using VRAM):
make up-vllm-fastcoder   # then: make ps-vllm, make logs-vllm-fastcoder, curl localhost:11434/v1/models
make down-vllm
```

#### 5. Fix-then-revert rule

If a major bump breaks something (import error, API change, startup crash):

1. **Try to fix forward first** — adapt the pin or the code. Examples:
   - A pip pin on top of a base image conflicts → align it with the version the
     base ships (from step 2), or drop the explicit install and inherit the base's copy.
   - An entrypoint uses an API removed in the new major line → update the call
     (e.g. huggingface_hub 1.x `scan_cache_dir()` raises `CacheNotFound` when
     `$HF_HOME/hub` does not exist yet; 0.x returned an empty result — guard with try/except).
   - Rebuild + re-run step 4 checks after each fix attempt.
2. **Revert only what cannot be fixed**, keeping the rest of the update set:

```bash
# revert specific versions in VERSIONS.env + affected Dockerfile ARGs, e.g.:
git diff VERSIONS.env compose/vllm/Dockerfile.vllm   # identify the lines
# then edit back to the old values (or: git checkout -- <files> if nothing else changed)
make config-all
conda run -n llama_infra python3 -m pytest -q tests/
make build-vllm                                    # rebuild reverted stack only
```

Never revert the whole batch when only one item is broken, and never delete
`./models` or `MODELS` data as a "fix" — model cache layouts (e.g. hf-hub's
`hub/models--*` dirs) are user data.

#### 6. Record the outcome

- The update manager auto-appends a CHANGELOG.md entry on apply; edit it if items
  were reverted afterward so it matches reality.
- Commit as `chore: bump tools/images to latest` (or split `chore:` + `fix:` when
  compatibility fixes were needed, e.g. entrypoint changes).
- If a new gotcha was discovered during the update, add a row to the Gotchas
  table in AGENTS.md.

#### Makefile gotchas that bite version updates

- `${VAR:-default}` in a recipe is **expanded by make, not bash** — make treats
  `VAR:-default` as an (undefined) variable name and substitutes empty text.
  Escape for bash with `$${VAR:-default}` (used by `smoke-vllm` /
  `pull-vllm-base`). Symptom: `docker pull some/image:` → "invalid reference format".
- Version variables flow `.env` → `VERSIONS.env` → Makefile vars → recipe env
  (`export` after the includes). Compose files reference bare `${VAR}`; the single
  source of truth is `VERSIONS.env`.

## Benchmarking & regression tracking

Two Python scripts under `scripts/` handle benchmarking and regression comparison.

### perf_test.py — run benchmarks

Measures TTFT, throughput, and duration per iteration via the Ollama `/api/chat` endpoint. Writes structured JSON to an output directory with a unique `run_id`.

```bash
# Single model, 5 iterations → writes to ./benchmarks/planner/results.json
python3 scripts/perf_test.py planner --iterations 5 --output-dir ./benchmarks/planner

# Multi-model + custom prompts file
python3 scripts/perf_test.py \
    --models coder,planner \
    --prompts-file workspace/prompts.txt \
    --max-tokens 256 \
    --iterations 5 \
    --output-dir ./benchmarks/run-$(date +%Y%m%d)

# JSON to stdout (no table)
python3 scripts/perf_test.py coder --json

# Or via Makefile shortcut:
make perf-test ARGS="--model planner --iterations 5"
```

Each `results.json` contains a flat list of per-iteration records with `run_id`, full prompt text, raw response output, per-iteration metrics, and combo-level aggregates.

### model_regression.py — compare against reference

Loads a previous `results.json` and compares every matched `(model, prompt)` combo for performance drift and output consistency.

```bash
# Compare latest run vs baseline; report written to ./regression-report/regression_report.json
python3 scripts/model_regression.py \
    --reference ./benchmarks/baseline/results.json \
    --output-dir ./regression-report

# Multiple current runs in one pass
python3 scripts/model_regression.py \
    --reference ref_results.json run1.json run2.json

# Pipe from stdin, custom thresholds (5 % warn / 8 % critical)
cat results.json | python3 scripts/model_regression.py \
    --reference ref_results.json --warn-threshold 5 --critical-threshold 8
```

Checks performed:
- **Performance regression** — percentage delta on `tokens_per_sec`, `first_token_ms`, `total_duration_s` (and their min/max variants). Warn ≥ threshold %, critical ≥ critical threshold %.
- **Output consistency** — are all iterations identical? (non-determinism) and how similar is the first iteration vs reference (`difflib.SequenceMatcher` ratio; < 80 % warn, < 50 % critical).

Exit codes: `0` = no regressions, `1` = critical found, `2` = warnings only.

## Code quality (pre-commit)

```bash
# install dev tooling
pip install -r requirements-dev.txt

# install git pre-commit hook
make precommit-install

# run all hooks manually
make precommit-run

# run focused agent routing verification
make verify-agent-routing

# refresh pinned hook revisions
make precommit-update
```

## Testing

The project uses pytest for unit and integration testing.

### Running tests

```bash
# Run all tests (requires conda environment)
conda run -n llama_infra python3 -m pytest -v tests/

# Run with coverage
conda run -n llama_infra python3 -m pytest --cov=. --cov-report=term-missing tests/

# Run specific test file
conda run -n llama_infra python3 -m pytest tests/test_perf_test.py
```

### Test structure

| File | Purpose |
|------|---------|
| `tests/test_agent_docs_check.py` | Validates `.github/agents/*.md` heading contract |
| `tests/test_perf_test.py` | Tests for benchmark result processing and formatting |
| `tests/test_update_manager.py` | Tests for Docker tag and PyPI version updates |

### Test coverage

- **Helper functions**: 100% coverage (e.g., `prompt_label`, `compute_aggregates`)
- **Network-dependent code**: Mocked tests for `update_manager` network calls
- **Integration tests**: Mock Ollama server for `run_benchmark` flow

### Writing tests

- Use `pytest-mock` for mocking network calls (`mocker` fixture)
- Use parametrized tests for edge cases (`@pytest.mark.parametrize`)
- Use `pytest-asyncio` for async integration tests
- Shared fixtures in `tests/conftest.py` (temp_dir, mock_agent_files, sample_benchmark_results)
