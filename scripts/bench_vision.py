#!/usr/bin/env python3
"""bench_vision.py — Benchmark multimodal (vision) capability of Ollama models.

Runs vision tests across multiple models and images, collecting timing metrics
and producing structured results.json for comparison/regression.

Uses /api/generate so chain-of-thought scaffolding is stripped from output.

Usage:
    python3 scripts/bench_vision.py --models fast-coder,planner --images img1.jpg,img2.jpg
    make bench-vision MODEL=fast-coder IMAGES=workspace/data/DOG_PARK-3-1024x576.jpg

Metrics per iteration:
  first_token_ms   — time to first token (TTFT)
  total_duration_s — wall-clock for full response
  input_tokens     — prompt/image token count
  output_tokens    — generated tokens
  eval_tps         — generation speed (tokens/sec)

Output format matches perf_test.py:
  results.json      — per-iteration records with raw_text and aggregates
  baseline.json     — last measured iteration per combo (for regression baselines)
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
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MAX_TOKENS = 512
DEFAULT_SYSTEM_PROMPT = "Answer concisely in one sentence."


def generate_run_id() -> str:
    """Generate a unique run identifier.

    Format: YYYYMMDD-HHMMSS-<6 random chars>
    """
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{timestamp}-{rand_suffix}"


def prompt_label(prompt: str, max_len: int = 28) -> str:
    """Return a short, readable label for a prompt string."""
    text = " ".join(prompt.split())
    if len(text) > max_len:
        return text[:max_len - 1] + "…"
    return text


def unique_prompt_label(label: str, seen_labels: set, max_len: int = 28) -> str:
    """Return a unique label for a prompt string, handling collisions."""
    if label not in seen_labels:
        seen_labels.add(label)
        return label

    hash_suffix = hashlib.md5(label.encode()).hexdigest()[:4]
    trunc_len = max_len - len(hash_suffix) - 1
    short_label = label[:trunc_len] if len(label) > trunc_len else label
    unique_label = f"{short_label}-{hash_suffix}"
    seen_labels.add(unique_label)
    return unique_label


@dataclass
class VisionResult:
    model: str
    image_file: str
    prompt_label: str
    first_token_ms: float
    total_duration_s: float
    input_tokens: int
    output_tokens: int
    eval_tps: float
    raw_text: str = ""


def run_vision_benchmark(
    model: str,
    image_path: str,
    prompt: str,
    system_prompt: str,
    max_tokens: int,
    timeout: int,
) -> Optional[VisionResult]:
    """Run a single vision benchmark iteration.

    Returns VisionResult on success, None if the request failed entirely.
    """
    base_url = DEFAULT_BASE_URL

    start_time = time.time()

    try:
        import requests
    except ImportError:
        print("Error: 'requests' package is required. Install with: pip install requests", file=sys.stderr)
        return None

    # Encode image to base64 for the API
    path = os.path.join(os.getcwd(), image_path) if not os.path.isabs(image_path) else image_path
    if not os.path.exists(path):
        print(f"Error: Image not found: {image_path}", file=sys.stderr)
        return None

    with open(path, "rb") as f:
        b64 = __import__("base64").b64encode(f.read()).decode("ascii")

    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": max_tokens},
    }

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        elapsed_s = time.time() - start_time
        first_token_ms = elapsed_s * 1000  # non-streaming: all tokens arrive at once

        if resp.status_code != 200:
            print(f"Error: Ollama returned HTTP {resp.status_code}", file=sys.stderr)
            return None

    except requests.RequestException as exc:
        print(f"Network error benchmarking {model}: {exc}", file=sys.stderr)
        return None

    data = resp.json()
    response_text = data.get("response", "") or ""
    output_tokens = int(data.get("eval_count", 0))
    input_tokens = int(data.get("prompt_eval_count", 0))
    eval_duration_s = data.get("eval_duration", 0) / 1e9 if isinstance(data.get("eval_duration"), (int, float)) else 0.0
    eval_tps = output_tokens / eval_duration_s if eval_duration_s > 0 else 0.0

    return VisionResult(
        model=model,
        image_file=os.path.basename(image_path),
        prompt_label=prompt_label(prompt),
        first_token_ms=first_token_ms,
        total_duration_s=elapsed_s,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        eval_tps=eval_tps,
        raw_text=response_text,
    )


def compute_aggregates(results: List[VisionResult]) -> dict:
    """Compute mean +/- min/max per metric for a group of results."""
    if not results:
        return {}

    first_token_ms = [r.first_token_ms for r in results]
    total_duration_s = [r.total_duration_s for r in results]
    input_tokens = [r.input_tokens for r in results]
    output_tokens = [r.output_tokens for r in results]
    eval_tps = [r.eval_tps for r in results]

    return {
        "iterations": results,
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
        "avg_eval_tps": sum(eval_tps) / len(eval_tps),
        "min_eval_tps": min(eval_tps),
        "max_eval_tps": max(eval_tps),
    }


def print_table(all_results: List[VisionResult]) -> None:
    """Print results in a formatted table with per-combo summary."""
    all_results.sort(key=lambda r: (r.model, r.image_file, r.prompt_label))

    # Group by (model, image, prompt)
    grouped: dict[tuple[str, str, str], list[VisionResult]] = {}
    for result in all_results:
        key = (result.model, result.image_file, result.prompt_label)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(result)

    # Print header
    print(f"{'Model':<14} | {'Image':<30} | {'Prompt':<28} | Tokens/s | First(ms) | Total(s) | In  | Out")
    print("-" * 115)

    for (model, imgfile, plabel), results in grouped.items():
        short_img = imgfile[:28] + ".." if len(imgfile) > 30 else imgfile
        short_plabel = plabel[:26] + ".." if len(plabel) > 28 else plabel

        for result in results:
            print(
                f"{result.model:<14} | {short_img:<30} | {short_plabel:<28} | "
                f"{result.eval_tps:>8.1f} | {result.first_token_ms:>9.1f} | "
                f"{result.total_duration_s:>8.2f} | {result.input_tokens:>3} | {result.output_tokens:>3}"
            )

        agg = compute_aggregates(results)
        if len(results) > 1:
            print(
                f"{'':<14} | {'':<30} | {'(summary)':<28} | "
                f"mean={agg['avg_eval_tps']:>7.1f}/min={agg['min_eval_tps']:.0f}/max={agg['max_eval_tps']:.0f}  "
                f"mean={agg['avg_first_token_ms']:>7.1f}/min={agg['min_first_token_ms']:.0f}/max={agg['max_first_token_ms']:.0f}  "
                f"mean={agg['avg_total_duration_s']:>7.2f}/min={agg['min_total_duration_s']:.2f}/max={agg['max_total_duration_s']:.2f}  "
                f"mean={agg['avg_input_tokens']:.0f}/{agg['min_input_tokens']:.0f}/{agg['max_input_tokens']:.0f}  "
                f"mean={agg['avg_output_tokens']:.0f}/{agg['min_output_tokens']:.0f}/{agg['max_output_tokens']:.0f}"
            )
        else:
            r = results[0]
            print(
                f"{'':<14} | {'':<30} | {'(summary)':<28} | "
                f"{r.eval_tps:>8.1f} | {r.first_token_ms:>9.1f} | {r.total_duration_s:>8.2f} | "
                f"{r.input_tokens:>3} | {r.output_tokens:>3}"
            )


def results_to_dicts(
    all_results: List[VisionResult],
    run_id: str,
) -> List[Dict[str, Any]]:
    """Convert VisionResults to a flat list of result records for JSON output."""
    grouped: dict[tuple[str, str, str], list[VisionResult]] = {}
    for result in all_results:
        key = (result.model, result.image_file, result.prompt_label)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(result)

    records: List[Dict[str, Any]] = []
    for (model, imgfile, plabel), results in sorted(grouped.items()):
        agg = compute_aggregates(results)
        for iter_idx, result in enumerate(results):
            iter_metrics = {k: v for k, v in asdict(result).items() if k != "raw_text"}
            records.append({
                "run_id": run_id,
                "model": model,
                "image_file": imgfile,
                "prompt_label": plabel,
                "iteration": iter_idx + 1,
                "raw_text": result.raw_text,
                "metrics": iter_metrics,
                "aggregates": {k: v for k, v in agg.items() if k != "iterations"},
            })

    return records


def filter_last_iteration(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only the last measured iteration per (model, image, prompt) combo."""
    grouped: dict[tuple[str, str, str], list[Dict[str, Any]]] = {}
    for rec in records:
        key = (rec.get("model"), rec.get("image_file"), rec.get("prompt_label"))
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(rec)

    return [grouped[k][-1] for k in sorted(grouped.keys())]


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Benchmark multimodal (vision) capability of Ollama models.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            '  python3 scripts/bench_vision.py --models fast-coder,planner \\\n'
            '      --images img1.jpg,img2.jpg --prompts "What is in this image?"\n'
            "  make bench-vision MODEL=fast-coder IMAGES=img.jpg"
        ),
    )

    parser.add_argument("--models", help="Comma-separated list of model names")
    parser.add_argument("--images", help="Comma-separated list of image paths (repeatable)")
    parser.add_argument(
        "--prompts", action="append", dest="prompts",
        help="Single prompt string (repeatable; default: 'What is in this image?')"
    )
    parser.add_argument(
        "--system", default=DEFAULT_SYSTEM_PROMPT,
        help=f"System instruction for the model (default: '{DEFAULT_SYSTEM_PROMPT}')"
    )
    parser.add_argument("--max-tokens", type=int, default=512, help="Max output tokens (default: 512)")
    parser.add_argument("--iterations", type=int, default=3, help="Iterations per combo (default: 3)")
    parser.add_argument("--output-dir", dest="output_dir", help="Directory for results.json")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Ollama base URL (default: http://localhost:11434)")
    parser.add_argument("--timeout", type=int, default=600, help="Per-request timeout in seconds (default: 600)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON to stdout")

    return parser


def main(argv=None) -> int:
    """Main entry point."""
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    # Handle models
    models = []
    if args.models:
        for m in args.models.split(","):
            m = m.strip()
            if m:
                models.append(m)
    if not models:
        print("Error: --models is required. Example: --models fast-coder,planner", file=sys.stderr)
        return 1

    # Handle images
    images = []
    if args.images:
        for img in args.images.split(","):
            img = img.strip()
            if img:
                images.append(img)
    if not images:
        print("Error: --images is required. Example: --images workspace/data/DOG_PARK-3-1024x576.jpg", file=sys.stderr)
        return 1

    # Handle prompts
    prompts = []
    if args.prompts:
        prompts.extend(args.prompts)
    if not prompts:
        prompts = ["What is in this image?"]

    run_id = generate_run_id()

    # Run benchmarks
    all_results: List[VisionResult] = []
    errors_occurred = False
    total_combos = len(models) * len(images) * len(prompts) * args.iterations
    combo_idx = 0

    for model in models:
        for image in images:
            for prompt in prompts:
                plabel = unique_prompt_label(
                    f"{prompt[:28]}@{os.path.basename(image)[:15]}", set()
                )
                for i in range(args.iterations):
                    combo_idx += 1
                    result = run_vision_benchmark(
                        model=model,
                        image_path=image,
                        prompt=prompt,
                        system_prompt=args.system,
                        max_tokens=args.max_tokens,
                        timeout=args.timeout,
                    )
                    if result:
                        if i == 0 and args.iterations > 1:
                            print(
                                f"[{combo_idx}/{total_combos}] iter {i + 1}: [warmup] "
                                f"{result.output_tokens} tok in {result.total_duration_s:.2f}s "
                                f"({result.eval_tps:.1f} t/s)",
                                file=sys.stderr,
                            )
                        else:
                            all_results.append(result)
                            print(
                                f"[{combo_idx}/{total_combos}] iter {i + 1}: "
                                f"{result.output_tokens} tok in {result.total_duration_s:.2f}s "
                                f"({result.eval_tps:.1f} t/s)",
                                file=sys.stderr,
                            )
                    else:
                        errors_occurred = True
                        print(f"[{combo_idx}/{total_combos}] iter {i + 1}: FAILED", file=sys.stderr)

    # Build structured records
    records = results_to_dicts(all_results, run_id)

    if not all_results:
        print("No results to report.", file=sys.stderr)
        return 1 if errors_occurred else 0

    # Print table (or JSON with --json flag)
    if args.json:
        aggregated: List[Dict[str, Any]] = []
        grouped: dict[tuple[str, str, str], list[VisionResult]] = {}
        for result in all_results:
            key = (result.model, result.image_file, result.prompt_label)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result)

        for (model, imgfile, plabel), results in sorted(grouped.items()):
            agg = compute_aggregates(results)
            agg["model"] = model
            agg["image_file"] = imgfile
            agg["prompt_label"] = plabel
            aggregated.append(agg)
        print(json.dumps(aggregated, indent=2))
    else:
        print_table(all_results)

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
                "images_count": len(images),
                "prompts_count": len(prompts),
                "results": records,
            }
            with open(results_path, "w") as f:
                json.dump(output_payload, f, indent=2)

            baseline_records = filter_last_iteration(records)
            baseline_payload = {
                "run_id": run_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "base_url": args.base_url,
                "max_tokens": args.max_tokens,
                "iterations": args.iterations,
                "models": sorted(models),
                "images_count": len(images),
                "prompts_count": len(prompts),
                "results": baseline_records,
            }
            baseline_path = os.path.join(args.output_dir, "baseline.json")
            with open(baseline_path, "w") as f:
                json.dump(baseline_payload, f, indent=2)

            print(f"\nResults written to {results_path}", file=sys.stderr)
            print(f"Baseline written to {baseline_path}", file=sys.stderr)
        except Exception as exc:
            print(f"Error writing results: {exc}", file=sys.stderr)
            errors_occurred = True

    return 1 if errors_occurred else 0


if __name__ == "__main__":
    sys.exit(main())
