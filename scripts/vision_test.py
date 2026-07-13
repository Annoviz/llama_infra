#!/usr/bin/env python3
"""vision_test.py — Test multimodal (image understanding) capability of an Ollama model.

Sends a base64-encoded image + prompt to the Ollama /api/chat endpoint and prints
the model's response along with timing info.

Usage:
    scripts/vision_test.py IMAGE_PATH [OPTIONS]
    make vision-test MODEL=fast-coder IMAGE=workspace/data/person.png

Options:
    --model NAME        Ollama model name  (default: fast-coder)
    --prompt TEXT       Prompt to send with the image  (default: "Describe this image in detail.")
    --max-tokens N      Max output tokens  (default: 512)
    --base-url URL      Ollama base URL  (default: http://localhost:11434)
    --timeout SECS      Per-request timeout  (default: 300)
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import requests


def encode_image(image_path: str) -> tuple[str, str]:
    """Read an image file and return (mime_type, base64_data).

    Supports PNG, JPEG, WEBP, GIF.
    """
    path = Path(image_path)
    if not path.exists():
        print(f"Error: Image file not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    ext = path.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
    mime_type = mime_map.get(ext)
    if not mime_type:
        print(f"Error: Unsupported image format '{ext}'. Supported: {', '.join(sorted(mime_map.keys()))}", file=sys.stderr)
        sys.exit(1)

    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return mime_type, b64


def vision_chat(base_url: str, model: str, image_b64: str, prompt: str, max_tokens: int, timeout: int) -> dict:
    """Send a multimodal chat request to Ollama and return the response."""
    url = f"{base_url.rstrip('/')}/api/chat"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": max_tokens,
        },
    }

    start = time.time()
    resp = requests.post(url, json=payload, timeout=timeout)
    elapsed_ms = (time.time() - start) * 1000

    if resp.status_code != 200:
        print(f"Error: Ollama returned HTTP {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    response_text = data.get("message", {}).get("content", "(empty response)")
    total_tokens = data.get("eval_count", 0) + data.get("load_prompt_details", {}).get("prompt_eval_count", 0) if isinstance(data.get("load_prompt_details"), dict) else 0
    eval_count = data.get("eval_count", 0)

    return {
        "response": response_text,
        "elapsed_ms": round(elapsed_ms, 1),
        "eval_count": eval_count,
        "total_tokens": total_tokens,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Test multimodal image understanding of an Ollama model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("image", help="Path to the image file (PNG, JPG, WEBP, GIF)")
    parser.add_argument("--model", default="fast-coder", help="Ollama model name (default: fast-coder)")
    parser.add_argument(
        "--prompt",
        default="Describe this image in detail. Identify objects, text, colors, and the overall scene.",
        help="Prompt to send with the image",
    )
    parser.add_argument("--max-tokens", type=int, default=512, help="Max output tokens (default: 512)")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--timeout", type=int, default=300, help="Request timeout in seconds (default: 300)")

    args = parser.parse_args()

    print(f"Model:       {args.model}")
    print(f"Image:       {args.image}")
    print(f"Max tokens:  {args.max_tokens}")
    print("-" * 60)

    _, image_b64 = encode_image(args.image)

    result = vision_chat(
        base_url=args.base_url,
        model=args.model,
        image_b64=image_b64,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )

    print(f"Time:        {result['elapsed_ms']} ms")
    print(f"Eval tokens: {result['eval_count']}")
    print("-" * 60)
    print()
    print(result["response"])


if __name__ == "__main__":
    main()
