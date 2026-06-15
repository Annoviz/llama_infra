#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# perf_test.sh — Benchmark Ollama models via the OpenAI-compatible API.
#
# Measures per-iteration:
#   time_to_first_token  (TTFT, ms)
#   total_time_ms        (wall-clock for full response)
#   tokens               (output token count from usage)
#   tokens_per_sec       (tokens / total_seconds)
#
# Usage:
#   scripts/perf_test.sh [MODEL ...] [OPTIONS]
#
# Options:
#   --prompt FILE|TEXT    Path to prompt file, or literal text with 'literal:' prefix
#   --max-tokens N        Max output tokens  (default: 128)
#   --iterations N        Number of iterations per model  (default: 3)
#   --output FILE         Write JSON results to this file
#   --base-url URL        Ollama base URL  (default: http://localhost:11434)
#   --timeout SECS        Per-request timeout  (default: 600)
# ---------------------------------------------------------------------------

exec python3 "$(dirname "$0")/perf_test.py" "$@"
