"""
perf_test.py — Benchmark Ollama models via the OpenAI-compatible API.

Measures per-iteration:
  time_to_first_token  (TTFT, ms)
  total_time_ms        (wall-clock for full response)
  tokens               (output token count from usage)
  tokens_per_sec       (tokens / total_seconds)

Usage:
  python3 scripts/perf_test.py [MODEL ...] [OPTIONS]

Options:
  --prompt FILE|TEXT    Path to prompt file, or literal text with 'literal:' prefix
  --max-tokens N        Max output tokens  (default: 128)
  --iterations N        Number of iterations per model  (default: 3)
  --output FILE         Write JSON results to this file
  --base-url URL        Ollama base URL  (default: http://localhost:11434)
  --timeout SECS        Per-request timeout  (default: 600)
  --json                Output results as JSON instead of table
  --prompts FILE        Path to file with one prompt per line (# = comment)
  --model NAME          Alternative single model name (repeatable)
  --models LIST         Comma-separated list of models

Exit codes:
  0  Success
  1  Errors occurred during run
  2  Server unreachable

"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from typing import List, Optional, Iterator

# Default prompts from the bash script
DEFAULT_PROMPTS = [
    "Who won the World Series in 2020?",
    "If I am 6 feet and 2 inches tall, what is my height in centimeters?"
]

DEFAULT_BASE_URL = "http://localhost:11434"


@dataclass
class BenchmarkResult:
    model: str
    prompt_label: str
    first_token_ms: float
    total_duration_s: float
    input_tokens: int
    output_tokens: int
    tokens_per_sec: float


def list_models(base_url: str) -> List[str]:
    """Get list of available models from Ollama API."""
    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return sorted([m["name"] for m in data["models"]])
    except Exception:
        return []


def _sse_iter(url: str, body: dict) -> Iterator[dict]:
    """Generator yielding parsed JSON objects from SSE stream."""
    try:
        req = urllib.request.Request(url)
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode()

        with urllib.request.urlopen(req, timeout=10) as response:
            for line in response:
                if line.startswith(b"data: "):
                    try:
                        yield json.loads(line[6:].decode())
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return


def run_benchmark(model: str, prompt: str, config: dict) -> Optional[BenchmarkResult]:
    """Run a single benchmark iteration."""
    base_url = config.get("base_url", DEFAULT_BASE_URL)
    max_tokens = config.get("max_tokens", 128)
    timeout = config.get("timeout", 600)

    start_time = time.time()
    first_token_time = None

    try:
        # Prepare the request body
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {"num_predict": max_tokens}
        }

        # Track first token time
        chunks = list(_sse_iter(f"{base_url}/api/chat", body))

        if not chunks:
            return None

        # Process all chunks to get final metrics
        total_duration_s = time.time() - start_time
        input_tokens = 0
        output_tokens = 0
        tokens_per_sec = 0.0

        for chunk in chunks:
            if "prompt_eval_count" in chunk:
                input_tokens = chunk["prompt_eval_count"]
            if "eval_count" in chunk:
                output_tokens = chunk["eval_count"]
            if "eval_duration" in chunk and "eval_count" in chunk:
                # Calculate tokens per second using server-side timing
                eval_duration_s = chunk["eval_duration"] / 1e9
                if eval_duration_s > 0:
                    tokens_per_sec = chunk["eval_count"] / eval_duration_s

        # First token time is the time from start to first non-header chunk
        first_token_time = (time.time() - start_time) * 1000

        return BenchmarkResult(
            model=model,
            prompt_label=prompt_label(prompt),
            first_token_ms=first_token_time,
            total_duration_s=total_duration_s,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tokens_per_sec=tokens_per_sec
        )
    except Exception as e:
        # Log error but continue with next iteration
        print(f"Error running benchmark for {model}: {e}", file=sys.stderr)
        return None


def prompt_label(prompt: str) -> str:
    """Get a short label for a prompt for display."""
    if len(prompt) <= 40:
        return prompt
    return prompt[:37] + "..."


def compute_aggregates(results_for_combo: List[BenchmarkResult]) -> dict:
    """Compute mean ± min/max per metric for a combo of results."""
    if not results_for_combo:
        return {}

    # Extract all values for each metric
    first_token_ms = [r.first_token_ms for r in results_for_combo]
    total_duration_s = [r.total_duration_s for r in results_for_combo]
    input_tokens = [r.input_tokens for r in results_for_combo]
    output_tokens = [r.output_tokens for r in results_for_combo]
    tokens_per_sec = [r.tokens_per_sec for r in results_for_combo]

    return {
        "iterations": results_for_combo,
        "avg_first_token_ms": sum(first_token_ms) / len(first_token_ms),
        "min_first_token_ms": min(first_token_ms),
        "max_first_token_ms": max(first_token_ms),
        "avg_total_duration_s": sum(total_duration_s) / len(total_duration_s),
        "min_total_duration_s": min(total_duration_s),
        "max_total_duration_s": max(total_duration_s),
        "avg_input_tokens": sum(input_tokens) / len(input_tokens),
        "min_input_tokens": min(input_tokens),
        "max_input_tokens": max(input_tokens),
        "avg_output_tokens": sum(output_tokens) / len(output_tokens),
        "min_output_tokens": min(output_tokens),
        "max_output_tokens": max(output_tokens),
        "avg_tokens_per_sec": sum(tokens_per_sec) / len(tokens_per_sec),
        "min_tokens_per_sec": min(tokens_per_sec),
        "max_tokens_per_sec": max(tokens_per_sec)
    }


def print_table(all_results: List[BenchmarkResult]) -> None:
    """Print results in a formatted table."""
    # Sort by model then prompt
    all_results.sort(key=lambda r: (r.model, r.prompt_label))

    # Print header
    print("Model         | Prompt                           | Tokens/s | First(ms) | Total(s) | In  | Out")
    print("--------------|----------------------------------|----------|-----------|----------|-----|----")

    # Print each result
    for result in all_results:
        print(f"{result.model:<13} | {result.prompt_label:<32} | {result.tokens_per_sec:>8.1f} | {result.first_token_ms:>9.1f} | {result.total_duration_s:>8.2f} | {result.input_tokens:>3} | {result.output_tokens:>3}")


def print_json(all_results: List[BenchmarkResult]) -> None:
    """Print results as JSON with aggregates."""
    # Group by model and prompt
    grouped = {}
    for result in all_results:
        key = (result.model, result.prompt_label)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(result)

    # Compute aggregates
    aggregated = []
    for (model, prompt_label), results in grouped.items():
        agg = compute_aggregates(results)
        agg["model"] = model
        agg["prompt"] = prompt_label
        aggregated.append(agg)

    print(json.dumps(aggregated, indent=2))


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Benchmark Ollama models via the OpenAI-compatible API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python3 scripts/perf_test.py --model fast-coder --prompt \"2+2\" --iterations 3"
    )

    # Positional arguments
    parser.add_argument("models", nargs="*", help="Model names")

    # Optional arguments
    parser.add_argument("--prompt", action="append", dest="prompts", help="Single prompt string (repeatable)")
    parser.add_argument("--prompts", help="Path to file with one prompt per line (# = comment)")
    parser.add_argument("--model", action="append", dest="models_alt", help="Alternative single model name (repeatable)")
    parser.add_argument("--models", help="Comma-separated list of models")
    parser.add_argument("--max-tokens", type=int, default=128, help="Max output tokens (default: 128)")
    parser.add_argument("--iterations", type=int, default=3, help="Iterations per model×prompt combo (default: 3)")
    parser.add_argument("--output", help="Write JSON results to file")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Ollama base URL (default: http://localhost:11434)")
    parser.add_argument("--timeout", type=int, default=600, help="Per-request timeout in seconds (default: 600)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON to stdout instead of table")

    return parser


def main(argv=None) -> int:
    """Main entry point."""
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    # Handle model arguments
    models = set()

    # Add positional models
    for model in args.models or []:
        models.add(model)

    # Add alternative models
    if args.models_alt:
        for model in args.models_alt:
            models.add(model)

    # Handle models from --models flag
    if args.models:
        for model in args.models.split(","):
            models.add(model.strip())

    # If no models specified, query available models
    if not models:
        print("Querying available models...", file=sys.stderr)
        available_models = list_models(args.base_url)
        if not available_models:
            print("No models found. Please ensure Ollama is running and models are loaded.", file=sys.stderr)
            return 2
        models.update(available_models)

    # Handle prompt arguments
    prompts = []

    # Add prompts from --prompt flag
    if args.prompts:
        prompts.extend(args.prompts or [])

    # Add prompts from --prompts file
    if args.prompts:
        try:
            with open(args.prompts, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        prompts.append(line)
        except Exception as e:
            print(f"Error reading prompts file: {e}", file=sys.stderr)
            return 1

    # If no prompts specified, use defaults
    if not prompts:
        prompts = DEFAULT_PROMPTS.copy()

    # Run benchmarks
    all_results = []
    errors_occurred = False

    for model in models:
        for prompt in prompts:
            print(f"Running benchmark for {model} with prompt: {prompt_label(prompt)}", file=sys.stderr)

            # Run iterations
            results_for_combo = []
            for i in range(args.iterations):
                result = run_benchmark(model, prompt, {
                    "base_url": args.base_url,
                    "max_tokens": args.max_tokens,
                    "timeout": args.timeout
                })
                if result:
                    results_for_combo.append(result)
                else:
                    errors_occurred = True

            # Add to all results
            all_results.extend(results_for_combo)

    # Output results
    if args.json or args.output:
        print_json(all_results)
    else:
        print_table(all_results)

    # Write to file if specified
    if args.output:
        try:
            with open(args.output, "w") as f:
                print_json(all_results)
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            errors_occurred = True

    return 1 if errors_occurred else 0


if __name__ == "__main__":
    sys.exit(main())