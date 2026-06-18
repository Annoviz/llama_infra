# model_regression.py

## Purpose

Compare benchmark runs against a reference results file. Performs performance regression detection and output consistency checks.

## Usage

```bash
python3 scripts/model_regression.py --reference ref_results.json [current_results.json ...]
python3 scripts/model_regression.py --reference ref_results.json --output-dir ./regression
```

## Arguments

- `--reference FILE` - Reference results.json to compare against (required)
- `--output-dir DIR` - Directory for regression report (auto-generated run_id)
- `--base-url URL` - Ollama base URL shown in the header
- `--warn-threshold PCT` - Warn if metric regresses by this % or more (default: 5)
- `--critical-threshold PCT` - Critical if metric regresses by this % or more (default: 10)

## Comparisons

### Performance Regression

Compares metrics between reference and current runs:
- **Higher is better**: tokens_per_sec, avg_tokens_per_sec
- **Lower is better**: first_token_ms, total_duration_s

### Output Consistency

Checks:
1. Are all iterations producing identical text? (internal consistency)
2. Is the output similar to the reference's last iteration?

## Exit Codes

- `0` - No regressions detected
- `1` - One or more critical regressions found
- `2` - One or more warnings (but no criticals)

## Examples

```bash
# Compare against reference
python3 scripts/model_regression.py --reference ref_results.json current_results.json

# Multiple current runs
python3 scripts/model_regression.py --reference ref.json run1.json run2.json

# Write report to directory
python3 scripts/model_regression.py --reference ref.json --output-dir ./regression
```

## See Also

- [bench.sh](bench.sh.md) - Benchmark runner that uses this tool
- [../operations.md](../operations.md) - Benchmarking guide
