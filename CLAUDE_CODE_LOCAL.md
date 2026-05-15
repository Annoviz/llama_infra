# Local Claude Code + Ollama Playbook (repo-aligned)

This guide is aligned with the current `llama_infra` repository workflow.
It assumes a Linux host with NVIDIA GPU support and Docker configured for GPUs.

## Scope and safety

- Main target stack: `docker-compose.yml` (`ollama-server`, optional UIs).
- Prefer Make targets when available (`make up-ollama`, `make logs-ollama`, etc.).
- Keep configuration layered: `.env` -> compose defaults -> container environment.
- Do not delete local model assets in `./models` unless you explicitly intend data loss.

## Phase 1 - Bring up Ollama with repo workflow

1. Review defaults in `docker-compose.yml` and optional overrides in `.env`.
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
docker compose -f docker-compose.yml exec -T ollama-server ollama --version
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
FROM qwen2.5-coder:14b
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

docker compose -f "$LLAMA_INFRA_DIR/docker-compose.yml" \
  exec -T ollama-server ollama create planner -f - < "$LLAMA_INFRA_DIR/workspace/models/Planner.Modelfile"

docker compose -f "$LLAMA_INFRA_DIR/docker-compose.yml" \
  exec -T ollama-server ollama create coder -f - < "$LLAMA_INFRA_DIR/workspace/models/Coder.Modelfile"

docker compose -f "$LLAMA_INFRA_DIR/docker-compose.yml" \
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

## Phase 5 - Lightweight benchmark script

`workspace/benchmark.py` is already committed in the repo. To run it:

```python
import time
import requests


def eval_speed(model_name: str) -> None:
    payload = {
        "model": model_name,
        "prompt": "Write a short Python function that validates IPv4 addresses.",
        "stream": False,
        "options": {"num_ctx": 4096},
    }

    started = time.time()
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=120,
        )
        elapsed = time.time() - started
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"[error] {model_name}: {exc}")
        return

    data = response.json()
    tokens = int(data.get("eval_count", 0))
    eval_duration_ns = int(data.get("eval_duration", 0))
    eval_seconds = eval_duration_ns / 1_000_000_000 if eval_duration_ns > 0 else 0.0
    tps = (tokens / eval_seconds) if eval_seconds > 0 else 0.0

    print(
        f"{model_name}: {tps:.2f} tok/s | tokens={tokens} "
        f"| eval_s={eval_seconds:.2f} | wall_s={elapsed:.2f}"
    )


if __name__ == "__main__":
    eval_speed("planner")
    eval_speed("coder")
```

Install dependency and run:

```bash
python3 -m pip install requests
python3 workspace/benchmark.py
```

## Troubleshooting quick checks

```bash
make ps-main
make logs-ollama
docker compose -f docker-compose.yml exec -T ollama-server ollama list
```

If you hit VRAM pressure, tune model context and parallelism first (`OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`, and per-model context settings) before changing disk/model layout.

