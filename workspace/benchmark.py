import time
import requests


def eval_speed(model_name: str) -> None:
    payload = {
        "model": model_name,
        "prompt": "Write a short Python function that validates IPv4 addresses.",
        "stream": False,
        "options": {"num_ctx": 4096},
    }

    started = time.time()
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=120,
        )
        elapsed = time.time() - started
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"[error] {model_name}: {exc}")
        return

    data = response.json()
    tokens = int(data.get("eval_count", 0))
    eval_duration_ns = int(data.get("eval_duration", 0))
    eval_seconds = eval_duration_ns / 1_000_000_000 if eval_duration_ns > 0 else 0.0
    tps = (tokens / eval_seconds) if eval_seconds > 0 else 0.0

    print(
        f"{model_name}: {tps:.2f} tok/s | tokens={tokens} "
        f"| eval_s={eval_seconds:.2f} | wall_s={elapsed:.2f}"
    )


if __name__ == "__main__":
    eval_speed("planner")
    eval_speed("coder")

