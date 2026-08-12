# Plan: Create `scripts/perf_test.py` — Ollama Performance Benchmark

## Context

The existing `scripts/perf_test.sh` is a 28-line shim that simply execs into `perf_test.py`, which doesn't exist yet. The bash script defines the CLI interface for benchmarking Ollama models via streaming API, measuring first-token latency, throughput, and token counts. We need to implement the Python backend while maintaining full backward compatibility with the existing flag conventions (`--prompt FILE|TEXT`, `--max-tokens N`, `--iterations N`, `--output FILE`, `--base-url URL`, `--timeout SECS`).

The project follows a stdlib-only convention for Python scripts (see [tools/update_manager.py](tools/update_manager.py): shebang, module docstring with usage/exit codes, `build_parser()` + `main(argv)` pattern, argparse-based CLI). No external dependencies exist in the project.

## Implementation Plan

### 1. Create `scripts/perf_test.py` — single file, stdlib only

**Module structure (in order):**
- Shebang + module docstring with usage examples and exit codes
- `from __future__ import annotations` + stdlib imports (`argparse`, `json`, `sys`, `time`, `urllib.request`, `dataclasses`)
- Constants: `DEFAULT_PROMPTS` (the two prompts from the bash script), default base URL, env var lookup
- Dataclass: `BenchmarkResult` — model, prompt_label, first_token_ms, total_duration_s, input_tokens, output_tokens, tokens_per_sec
- API functions using `urllib.request`:
  - `list_models(base_url)` → sorted list of available model names from `/api/tags`
  - `_sse_iter(url, body)` → generator yielding parsed JSON objects from SSE stream
  - `run_benchmark(model, prompt, config)` → BenchmarkResult via streaming API (default) or non-streaming fallback
- Helper functions:
  - `prompt_label(prompt)` — first 40 chars + "..." for table display
  - `compute_aggregates(results_for_combo)` → mean ± min/max per metric
  - `print_table(all_results)` — formatted columnar output using fixed-width columns
  - `print_json(all_results)` — JSON array with per-combo aggregates (for `--json` flag)
- CLI layer: `build_parser()` matching the bash script's existing flags exactly, plus extras
- Entry point: `main(argv=None)` → parse args → resolve models/prompts → run iterations → output

### 2. CLI flags (backward-compatible with perf_test.sh + additions)

| Flag | Description |
|------|-------------|
| Positional `MODEL ...` | Model names, matching the bash script's `perf_test.sh [MODEL ...]` syntax |
| `-p TEXT` or `--prompt TEXT` | Single prompt string (repeatable) — like bash's repeated `--prompt` |
| `--prompts FILE` | Path to file with one prompt per line (`#` = comment) — new convenience flag |
| `-m NAME` or `--model NAME` | Alternative single model name (repeatable, additive with positional args) |
| `--models LIST` | Comma-separated list of models |
| `--max-tokens N` | Max output tokens (default: 128, matches bash) |
| `--iterations N` | Iterations per model×prompt combo (default: 3, matches bash) |
| `--output FILE` | Write JSON results to file (matches bash) |
| `--base-url URL` | Ollama server URL (default: http://localhost:11434, matches bash) |
| `--timeout SECS` | Per-request timeout in seconds (default: 600, matches bash) |
| `--json` | Output results as JSON to stdout instead of table — new convenience flag |

**Auto-discovery:** If no models specified via flags, query `/api/tags` and use all loaded models.

### 3. API integration

Use Ollama's `/api/chat` endpoint with `"stream": true`. The streaming SSE response yields per-chunk JSON objects containing `done`, `model`, `total_duration`, `prompt_eval_count`, `eval_count`, `eval_duration`, etc. Key design:
- **First token latency**: wall-clock time from request send to first non-header chunk arrival
- **Total timing + tokens**: extracted from the final SSE chunk where `"done": true`
- **Tokens/sec**: `output_tokens / (eval_duration_ns / 1e9)` — uses server-side timing, not wall-clock

### 4. Output format

**Table mode** (default): Fixed-width columns, sorted by model then prompt:

```
Model         | Prompt                           | Tokens/s | First(ms) | Total(s) | In  | Out
--------------|----------------------------------|----------|-----------|----------|-----|----
fast-coder    | Who won the World Series in...   |     450.6|      15.3 |     0.04 |  32 |  15
planner       | Who won the World Series in...   |     142.3|      85.2 |     1.20 |  32 | 171
```

**JSON mode** (`--json` or `--output FILE`): Array of objects with per-combo aggregates:

```json
[{"model": "planner", "prompt": "...", "iterations": [...],
  "avg_tokens_per_sec": 142.3, "avg_first_token_ms": 85.2, ...}]
```

### 5. Error handling

- Server unreachable → print to stderr, exit code 2
- Model not loaded (not in `/api/tags`) → warning to stderr, skip that model
- Individual iteration failures → log to stderr, continue with next iteration
- Division by zero in tokens/sec → report `0.0` or `inf`, never crash
- Exit code 1 if any errors occurred during the run

### 6. Verification steps

1. Run `python3 scripts/perf_test.py --help` — should show all flags with descriptions
2. Run against a loaded model: `python3 scripts/perf_test.py --model fast-coder --prompt "2+2" --iterations 3`
3. Verify output matches expected metrics (tokens, first token latency, tokens/sec)
4. Test JSON output: `python3 scripts/perf_test.py --model fast-coder --json`
5. Verify backward compatibility: `scripts/perf_test.sh fast-coder --max-tokens 64 --iterations 2` should work identically to the Python script

## Critical Files

- **Creates**: `scripts/perf_test.py` — new benchmark implementation
- **Reference (CLI compat)**: [scripts/perf_test.sh](scripts/perf_test.sh) — defines existing flag conventions this must match
- **Reference (Python style)**: [tools/update_manager.py](tools/update_manager.py) — stdlib-only script pattern used in this project
