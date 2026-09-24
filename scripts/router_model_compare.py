#!/usr/bin/env python3
"""Benchmark runner for Qwen3.6-35B, Qwen3.8-27B, and Ternary-Bonsai-2-27B.

This script is designed to compare three router-mode models in a controlled way:
- run stock Qwen models with PRISM_LM=0
- run Ternary with PRISM_LM=1
- run both a text prompt benchmark and a fixed image-description benchmark
- save a structured JSON summary per model and per phase

The goal is to keep the same hardware, same prompt, same image, and same router
configuration while toggling the runtime binary by recreating the service.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_ENV = REPO_ROOT / "VERSIONS.env"


def normalize_prompt(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt).strip()


def build_model_specs() -> List[Dict[str, Any]]:
    complex_prompt = (
        "You are benchmarking a long-context reasoning model. Explain the trade-offs between GPU offload, "
        "KV-cache quantization, speculative decoding, and context length tuning for a 27B or 35B model serving on a "
        "single GPU. Give a concrete recommendation for a production deployment, including memory pressure, "
        "latency, and quality trade-offs."
    )
    return [
        {
            "name": "Qwen3.6-35B",
            "prism_lm": 0,
            "preset": "Qwen3.6-35B",
            "prompt": complex_prompt,
            "description": "Stock llama.cpp path for Qwen3.6-35B benchmark.",
        },
        {
            "name": "Qwen3.8-27B",
            "prism_lm": 0,
            "preset": "Qwen3.8-27B",
            "prompt": complex_prompt,
            "description": "Stock llama.cpp path for standard Qwen3.8-27B benchmark.",
        },
        {
            "name": "Ternary-Bonsai-2-27B",
            "prism_lm": 1,
            "preset": "Ternary-Bonsai-2-27B",
            "prompt": complex_prompt,
            "description": "PrismML path for Ternary-Bonsai-2-27B benchmark.",
        },
    ]


def prompt_variants() -> List[str]:
    return [
        "This is a complex benchmark prompt for a long-context reasoning model. Explain the trade-offs between GPU offload, KV-cache quantization, speculative decoding, and context length tuning for a 27B model serving on a single GPU. Give a concrete recommendation for a production deployment, including memory pressure, latency, and quality trade-offs.",
        "Describe this image in detail. Identify the main objects, the scene layout, any visible text, colors, composition, and plausible context. Keep the answer concise but informative.",
    ]


def set_prism_lm(value: int) -> None:
    if value not in (0, 1):
        raise ValueError(f"PRISM_LM must be 0 or 1, got {value}")

    if not VERSIONS_ENV.exists():
        raise FileNotFoundError(f"Missing {VERSIONS_ENV}")

    text = VERSIONS_ENV.read_text(encoding="utf-8")
    lines = text.splitlines()
    updated = False
    for idx, line in enumerate(lines):
        if line.startswith("PRISM_LM="):
            lines[idx] = f"PRISM_LM={value}"
            updated = True
            break

    if not updated:
        lines.append(f"PRISM_LM={value}")

    VERSIONS_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def recreate_router_service() -> float:
    start = time.time()
    commands = [
        ["make", "down-llamacpp-router"],
        ["make", "up-llamacpp-router"],
    ]
    for cmd in commands:
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    return round(time.time() - start, 3)


def read_image(prompt_file: str | None = None) -> str:
    if prompt_file:
        return str(Path(prompt_file).resolve())
    default = REPO_ROOT / "workspace" / "data"
    if default.exists():
        candidates = sorted(default.glob("*"))
        if candidates:
            return str(candidates[0])
    return str((REPO_ROOT / "workspace" / "data" / "person.png").resolve())


def read_and_encode_image(image_path: str) -> str:
    path = Path(image_path).resolve()
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/png")
    raw = path.read_bytes()
    return f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"


def extract_timing_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    timings = data.get("timings", {})
    metrics: Dict[str, Any] = {
        "prompt_tokens": timings.get("prompt_n"),
        "prompt_ms": timings.get("prompt_ms"),
        "prompt_tokens_per_second": timings.get("prompt_per_second"),
        "prompt_eval_tokens_per_second": timings.get("prompt_per_second"),
        "generation_tokens": timings.get("predicted_n"),
        "generation_ms": timings.get("predicted_ms"),
        "generation_tokens_per_second": timings.get("predicted_per_second"),
        "decode_tokens_per_second": timings.get("predicted_per_second"),
        "draft_tokens": timings.get("draft_n"),
        "draft_tokens_accepted": timings.get("draft_n_accepted"),
        "draft_ms": timings.get("draft_ms"),
    }
    if metrics["draft_tokens"] and metrics["draft_ms"]:
        metrics["draft_tokens_per_second"] = metrics["draft_tokens"] / (metrics["draft_ms"] / 1000)
    else:
        metrics["draft_tokens_per_second"] = None
    return metrics


def run_vision_test(image_path: str, model: str, prompt: str) -> Dict[str, Any]:
    url = "http://localhost:8080/v1/chat/completions"
    payload = {
        "model": model,
        "max_tokens": 512,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "Answer concisely in one sentence."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": read_and_encode_image(image_path)}},
                ],
            },
        ],
    }
    t0 = time.time()
    resp = requests.post(url, json=payload, timeout=300)
    elapsed_ms = (time.time() - t0) * 1000
    data = resp.json()
    if resp.status_code != 200:
        raise RuntimeError(f"vision test failed for {model}: {data}")
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return {
        "model": model,
        "elapsed_ms": round(elapsed_ms, 1),
        "completion_tokens": usage.get("completion_tokens", 0),
        "timings": extract_timing_metrics(data),
        "response": text,
    }


def run_text_benchmark(model: str, prompt: str, iterations: int = 3) -> Dict[str, Any]:
    all_results: List[Dict[str, Any]] = []
    for _ in range(iterations):
        payload = {
            "model": model,
            "max_tokens": 256,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}],
        }
        t0 = time.time()
        resp = requests.post("http://localhost:8080/v1/chat/completions", json=payload, timeout=300)
        elapsed = time.time() - t0
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(f"text benchmark failed for {model}: {data}")
        msg = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        all_results.append(
            {
                "model": model,
                "elapsed_s": round(elapsed, 3),
                "completion_tokens": usage.get("completion_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "timings": extract_timing_metrics(data),
                "response": msg,
            }
        )

    return {"model": model, "iterations": iterations, "results": all_results}


def summarize_text_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    measured_results = results[1:]
    latencies = [item["elapsed_s"] for item in measured_results]
    timing_metrics = [item["timings"] for item in measured_results]
    generation_rates = [item["generation_tokens_per_second"] for item in timing_metrics if item["generation_tokens_per_second"]]
    prompt_rates = [item["prompt_tokens_per_second"] for item in timing_metrics if item["prompt_tokens_per_second"]]
    draft_rates = [item["draft_tokens_per_second"] for item in timing_metrics if item["draft_tokens_per_second"]]

    return {
        "measured_text_iterations": len(measured_results),
        "repeat_mean_elapsed_s": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        "repeat_mean_tokens_per_second": {
            "prompt_processing": round(sum(prompt_rates) / len(prompt_rates), 3) if prompt_rates else None,
            "prompt_eval": round(sum(prompt_rates) / len(prompt_rates), 3) if prompt_rates else None,
            "decode": round(sum(generation_rates) / len(generation_rates), 3) if generation_rates else None,
            "generation": round(sum(generation_rates) / len(generation_rates), 3) if generation_rates else None,
            "speculative_draft": round(sum(draft_rates) / len(draft_rates), 3) if draft_rates else None,
        },
    }


def run_case(model_spec: Dict[str, Any], image_path: str, iterations: int = 3) -> Dict[str, Any]:
    model_name = model_spec["name"]
    prompt = normalize_prompt(model_spec["prompt"])
    vision_prompt = "Describe this image in detail. Identify the main objects, the scene, any visible text, and the overall mood."

    cold_start_seconds = recreate_router_service()
    text_result = run_text_benchmark(model_name, prompt, iterations=iterations)
    vision_result = run_vision_test(image_path, model_name, vision_prompt)

    summary = summarize_text_results(text_result["results"])

    return {
        "model": model_name,
        "prism_lm": model_spec["prism_lm"],
        "preset": model_spec["preset"],
        "cold_start_seconds": cold_start_seconds,
        "text": text_result,
        "warmup_excluded": {
            "text_result_index": 0,
            "measured_text_iterations": summary["measured_text_iterations"],
        },
        "repeat_mean_elapsed_s": summary["repeat_mean_elapsed_s"],
        "repeat_mean_tokens_per_second": summary["repeat_mean_tokens_per_second"],
        "vision": vision_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare Qwen3.6-35B, Qwen3.8-27B, and Ternary-Bonsai-2-27B via the llama.cpp router"
    )
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--image", default=None)
    args = parser.parse_args()

    image_path = read_image(args.image)
    results: List[Dict[str, Any]] = []

    for spec in build_model_specs():
        set_prism_lm(spec["prism_lm"])
        results.append(run_case(spec, image_path, iterations=args.iterations))

    out_path = REPO_ROOT / "benchmarks" / "llama-router-qwen-vs-ternary-vs-qwen36.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(json.dumps({"saved_to": str(out_path), "models": [r["model"] for r in results]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
