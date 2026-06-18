# bench.sh

## Purpose

Model benchmark runner with optional regression comparison. Runs performance tests and compares results against a baseline.

## Usage

```bash
scripts/bench.sh <model_flavor> --output-dir <dir> [extra args ...]
```

## Arguments

- `model_flavor` - One of: `planner`, `coder`, `fast-coder` (custom names, not Ollama IDs)
- `--output-dir DIR` - Directory for results.json (created if needed)
- `extra args` - Passed through to perf_test.sh

## Regression Comparison

If `<dir>/reg-results.json` exists, compares current results against it. If not found, saves the last-iteration results as reg-results.json so future runs have a reference.

## Examples

```bash
# Benchmark planner model
scripts/bench.sh planner --output-dir benchmarks/planner

# Benchmark coder model with custom iterations
scripts/bench.sh coder --output-dir benchmarks/coder --iterations 5

# Run with regression comparison
scripts/bench.sh fast-coder --output-dir benchmarks/fast-coder
```

## Exit Codes

- `0` - Success (no regressions or baseline saved)
- `1` - Critical regression detected
- `2` - Warning threshold exceeded

## See Also

- [perf_test.sh](perf_test.sh.md) - Core performance test runner
- [model_regression.py](model_regression.py.md) - Regression comparison logic
- [../operations.md](../operations.md) - Benchmarking guide
