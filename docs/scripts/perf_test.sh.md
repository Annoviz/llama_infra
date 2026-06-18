# perf_test.sh

## Purpose

Performance test runner for Ollama models via the OpenAI-compatible API. Measures timing metrics and token throughput.

## Usage

```bash
scripts/perf_test.sh [MODEL ...] [OPTIONS]
```

## Options

- `--prompt FILE\|TEXT` - Path to prompt file, or literal text with 'literal:' prefix
- `--max-tokens N` - Max output tokens (default: 128)
- `--iterations N` - Number of iterations per model (default: 3)
- `--output FILE` - Write JSON results to this file
- `--base-url URL` - Ollama base URL (default: http://localhost:11434)
- `--timeout SECS` - Per-request timeout (default: 600)

## Metrics Measured

- `time_to_first_token` (TTFT, ms)
- `total_time_ms` (wall-clock for full response)
- `tokens` (output token count from usage)
- `tokens_per_sec` (tokens / total_seconds)

## Examples

```bash
# Test with default settings
scripts/perf_test.sh --model planner

# Custom prompt and iterations
scripts/perf_test.sh --model coder --iterations 5 --max-tokens 256

# Use literal prompt text
scripts/perf_test.sh --model fast-coder --prompt "literal:Write a hello world script"
```

## See Also

- [bench.sh](bench.sh.md) - Benchmark runner with regression comparison
- [model_regression.py](model_regression.py.md) - Regression comparison tool
