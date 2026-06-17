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
  --output-dir DIR      Directory for results.json (auto-generated run_id)
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
import hashlib
import json
import os
import random
import string
import sys
import time
import urllib.request
import urllib.error
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


# Default prompts from the bash script
DEFAULT_PROMPTS = [
    "Who won the World Series in 2020?",
    "If I am 6 feet and 2 inches tall, what is my height in centimeters?",
    "write highly complex python code for threaded video processing"
]

DEFAULT_BASE_URL = "http://localhost:11434"


def generate_run_id() -> str:
    """Generate a unique run identifier.

    Format: YYYYMMDD-HHMMSS-<6 random chars>
    Example: 20260615-143022-a7b3c9
    """
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{timestamp}-{rand_suffix}"


def prompt_label(prompt: str, max_len: int = 28) -> str:
    """Return a short, readable label for a prompt string.

    Truncates to *max_len* chars and appends '…' if longer.
    Collapses internal whitespace runs into single spaces.
    """
    text = " ".join(prompt.split())
    if len(text) > max_len:
        return text[:max_len - 1] + "…"
    return text


@dataclass
class BenchmarkResult:
    model: str
    prompt_label: str
    first_token_ms: float
    total_duration_s: float
    input_tokens: int
    output_tokens: int
    tokens_per_sec: float
    # Optional fields filled during collection
    raw_text: str = ""


def list_models(base_url: str) -> List[str]:
    """Get list of available models from Ollama API."""
    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return sorted([m["name"] for m in data["models"]])
    except Exception:
        return []


def run_benchmark(model: str, prompt: str, config: dict) -> Optional[BenchmarkResult]:
    """Run a single benchmark iteration.

    Returns (BenchmarkResult | None): result on success, None if the request
    failed entirely (network error, empty response, etc.).  Errors are logged
    to stderr so they don't silently disappear from the user's view.
    """
    base_url = config.get("base_url", DEFAULT_BASE_URL)
    max_tokens = config.get("max_tokens", 128)
    timeout = config.get("timeout", 600)

    start_time = time.time()
    first_token_ms: float = -1.0
    raw_text_parts: List[str] = []

    try:
        # Prepare the request body
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {"num_predict": max_tokens}
        }

        # Track first token time as soon as we see the first chunk
        first_chunk_seen = False
        input_tokens = 0
        output_tokens = 0
        tokens_per_sec = 0.0

        req = urllib.request.Request(f"{base_url}/api/chat", method="POST")
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode()

        with urllib.request.urlopen(req, timeout=timeout) as response:
            for raw_line in response:
                line = raw_line.strip()
                if not line:
                    continue

                # Strip OpenAI-style SSE prefix (Ollama sends bare JSONL)
                if line.startswith(b"data: "):
                    line = line[6:]
                elif line == b"[DONE]":
                    continue

                try:
                    chunk = json.loads(line.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                # Capture raw output text from content field
                message = chunk.get("message", {})
                if message.get("role") == "assistant" and "content" in message:
                    raw_text_parts.append(message["content"])

                # Measure wall-clock from request start to first data chunk
                if not first_chunk_seen:
                    first_token_ms = (time.time() - start_time) * 1000
                    first_chunk_seen = True

                # Accumulate metrics — Ollama may emit these in the same chunk
                if "prompt_eval_count" in chunk:
                    input_tokens = chunk["prompt_eval_count"]
                if "eval_count" in chunk:
                    output_tokens = chunk["eval_count"]
                if "eval_duration" in chunk and "eval_count" in chunk:
                    eval_duration_s = chunk["eval_duration"] / 1e9
                    if eval_duration_s > 0:
                        tokens_per_sec = chunk["eval_count"] / eval_duration_s

        total_duration_s = time.time() - start_time

        # Guard against empty response (no chunks emitted at all)
        if not first_chunk_seen:
            print(f"Empty response from {model}", file=sys.stderr)
            return None

        return BenchmarkResult(
            model=model,
            prompt_label=prompt_label(prompt),
            first_token_ms=first_token_ms,
            total_duration_s=total_duration_s,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tokens_per_sec=tokens_per_sec,
            raw_text="".join(raw_text_parts)
        )

    except urllib.error.URLError as e:
        print(f"Network error benchmarking {model}: {e.reason}", file=sys.stderr)
        return None
    except TimeoutError:
        print(f"Timeout benchmarking {model} ({timeout}s limit)", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error running benchmark for {model}: {type(e).__name__}: {e}", file=sys.stderr)
        return None


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
    """Print results in a formatted table with per-combo summary."""
    # Sort by model then prompt
    all_results.sort(key=lambda r: (r.model, r.prompt_label))

    # Group by (model, prompt)
    grouped: dict[tuple[str, str], list[BenchmarkResult]] = {}
    for result in all_results:
        key = (result.model, result.prompt_label)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(result)

    # Print header
    print("Model         | Prompt                       | Tokens/s | First(ms) | Total(s) | In  | Out")
    print("--------------|------------------------------|----------|-----------|----------|-----|----")

    for (model, plabel), results in grouped.items():
        # Individual iterations
        for result in results:
            print(f"{result.model:<13} | {plabel:<28} | {result.tokens_per_sec:>8.1f} | {result.first_token_ms:>9.1f} | {result.total_duration_s:>8.2f} | {result.input_tokens:>3} | {result.output_tokens:>3}")

        # Summary row
        agg = compute_aggregates(results)
        if len(results) > 1:
            print(f"{model:<13} | {'(summary)':<28} | "
                  f"mean={agg['avg_tokens_per_sec']:>7.1f}/min={agg['min_tokens_per_sec']:.0f}/max={agg['max_tokens_per_sec']:.0f}  "
                  f"mean={agg['avg_first_token_ms']:>7.1f}/min={agg['min_first_token_ms']:.0f}/max={agg['max_first_token_ms']:.0f}  "
                  f"mean={agg['avg_total_duration_s']:>7.2f}/min={agg['min_total_duration_s']:.2f}/max={agg['max_total_duration_s']:.2f}  "
                  f"mean={agg['avg_input_tokens']:.0f}/{agg['min_input_tokens']:.0f}/{agg['max_input_tokens']:.0f}  "
                  f"mean={agg['avg_output_tokens']:.0f}/{agg['min_output_tokens']:.0f}/{agg['max_output_tokens']:.0f}")
        else:
            print(f"{model:<13} | {'(summary)':<28} | {results[0].tokens_per_sec:>8.1f} | {results[0].first_token_ms:>9.1f} | {results[0].total_duration_s:>8.2f} | {results[0].input_tokens:>3} | {results[0].output_tokens:>3}")


def results_to_dicts(all_results: List[BenchmarkResult], run_id: str,
                     prompts_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """Convert BenchmarkResults to a flat list of result records for JSON output.

    Each record contains:
      - run_id: the unique identifier for this benchmark run
      - model: model name
      - prompt: full original prompt text (looked up via prompt_label)
      - prompt_label: short label used in tables/keys
      - iteration: 0-based iteration index within the combo
      - raw_text: the assistant's full response text
      - metrics: dict of numeric metrics for this iteration

    Returns a list sorted by (model, prompt_label, iteration).
    """
    # Group by (model, prompt_label) to assign iteration indices
    grouped: dict[tuple[str, str], list[BenchmarkResult]] = {}
    for result in all_results:
        key = (result.model, result.prompt_label)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(result)

    records: List[Dict[str, Any]] = []
    for (model, plabel), results in sorted(grouped.items()):
        # Compute aggregates for this combo and attach to each record
        agg = compute_aggregates(results)
        prompts_map[(model, plabel)] = None  # placeholder; caller fills

        # Safety net: skip iteration 0 (warmup). Redundant with the collection loop,
        # but kept for backward compat if old reg-results.json files contain iteration 0 records.
        for idx, result in enumerate(results):
            if idx == 0:
                continue

            iter_metrics = {k: v for k, v in asdict(result).items() if k != "raw_text"}
            records.append({
                "run_id": run_id,
                "model": model,
                "prompt_label": plabel,
                "iteration": idx,
                "raw_text": result.raw_text,
                "metrics": iter_metrics,
                "aggregates": {k: v for k, v in agg.items() if k != "iterations"},
            })

    return records


def filter_last_iteration(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only the last measured iteration per (model, prompt_label) combo.

    Skips warmup iterations (iteration == 0). Useful for regression baselines
    where a single representative result per combo is sufficient.
    """
    # Group by combo preserving insertion order
    grouped: dict[tuple[str, str], list[Dict[str, Any]]] = {}
    for rec in records:
        key = (rec.get("model"), rec.get("prompt_label"))
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(rec)

    # Keep last non-warmup iteration per combo
    return [grouped[k][-1] for k in sorted(grouped.keys())]


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
    for (model, plabel), results in grouped.items():
        agg = compute_aggregates(results)
        agg["model"] = model
        agg["prompt"] = plabel
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
    parser.add_argument("--prompts-file", dest="prompts_file", help="Path to file with one prompt per line (# = comment)")
    parser.add_argument("--model", action="append", dest="models_alt", help="Alternative single model name (repeatable)")
    parser.add_argument("--models", help="Comma-separated list of models")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Max output tokens (default: 2048)")
    parser.add_argument("--iterations", type=int, default=3, help="Iterations per model×prompt combo (default: 3)")
    parser.add_argument("--output", help="Write JSON results to this file")
    parser.add_argument("--output-dir", dest="output_dir", help="Directory for auto-generated results.json (run_id-based)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Ollama base URL (default: http://localhost:11434)")
    parser.add_argument("--timeout", type=int, default=600, help="Per-request timeout in seconds (default: 600)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON to stdout instead of table")
    parser.add_argument("--save-baseline", dest="save_baseline", action="store_true",
                        help="Also write baseline.json (last measured iteration per combo, "
                             "warmup skipped) — for regression baselines")

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

    # Add prompts from --prompts-file argument
    if args.prompts_file:
        try:
            with open(args.prompts_file, "r") as f:
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

    # Generate run_id and build prompt label -> original text map
    run_id = generate_run_id()
    prompt_label_to_text: dict[tuple[str, str], str] = {}  # (model, label) → full prompt
    for model in sorted(models):
        for prompt in prompts:
            key = (model, prompt_label(prompt))
            prompt_label_to_text[key] = prompt

    # Run benchmarks
    all_results = []
    errors_occurred = False
    total_combos = len(models) * len(prompts)
    combo_idx = 0

    for model in models:
        for prompt in prompts:
            combo_idx += 1
            plabel = prompt_label(prompt)
            print(
                f"[{combo_idx}/{total_combos}] {model} — {plabel}",
                file=sys.stderr,
            )

            # Run iterations — iteration 0 is a warmup, run it but don't store.
            for i in range(args.iterations):
                result = run_benchmark(model, prompt, {
                    "base_url": args.base_url,
                    "max_tokens": args.max_tokens,
                    "timeout": args.timeout
                })
                if result:
                    # Skip warmup iteration (index 0) — store only measured runs.
                    if i == 0 and args.iterations > 1:
                        print(
                            f"  iter {i + 1}/{args.iterations}: [warmup] "
                            f"{result.output_tokens} tok in {result.total_duration_s:.2f}s "
                            f"({result.tokens_per_sec:.1f} t/s)",
                            file=sys.stderr,
                        )
                    else:
                        all_results.append(result)
                        print(
                            f"  iter {i + 1}/{args.iterations}: "
                            f"{result.output_tokens} tok in {result.total_duration_s:.2f}s "
                            f"({result.tokens_per_sec:.1f} t/s)",
                            file=sys.stderr,
                        )
                else:
                    errors_occurred = True
                    print(f"  iter {i + 1}/{args.iterations}: FAILED", file=sys.stderr)

    # Build structured records with run_id, full prompts, and raw text
    records = results_to_dicts(all_results, run_id, prompt_label_to_text)

    # Fill in full prompt text into each record
    for rec in records:
        key = (rec["model"], rec["prompt_label"])
        rec["prompt"] = prompt_label_to_text.get(key, rec["prompt_label"])

    # Write to --output file if specified
    if args.output:
        try:
            with open(args.output, "w") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            errors_occurred = True

    # Write results.json into --output-dir if specified
    if args.output_dir:
        try:
            os.makedirs(args.output_dir, exist_ok=True)
            results_path = os.path.join(args.output_dir, "results.json")
            output_payload = {
                "run_id": run_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "base_url": args.base_url,
                "max_tokens": args.max_tokens,
                "iterations": args.iterations,
                "models": sorted(models),
                "prompts_count": len(prompts),
                "results": records,
            }
            with open(results_path, "w") as f:
                json.dump(output_payload, f, indent=2)

            # Write baseline.json (last measured iteration per combo, warmup skipped).
            if args.save_baseline:
                baseline_records = filter_last_iteration(records)
                baseline_payload = {
                    "run_id": run_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "base_url": args.base_url,
                    "max_tokens": args.max_tokens,
                    "iterations": args.iterations,
                    "models": sorted(models),
                    "prompts_count": len(prompts),
                    "results": baseline_records,
                }
                baseline_path = os.path.join(args.output_dir, "baseline.json")
                with open(baseline_path, "w") as f:
                    json.dump(baseline_payload, f, indent=2)
                print(f"Baseline written to {baseline_path}", file=sys.stderr)

            print(f"\nResults written to {results_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing to output directory: {e}", file=sys.stderr)
            errors_occurred = True

    return 1 if errors_occurred else 0


if __name__ == "__main__":
    sys.exit(main())
