# Qwen3.6-35B vs Qwen3.8-27B vs Ternary-Bonsai-2-27B router benchmark

## Scope
This benchmark compares three models served through the llama.cpp router stack in this repo:

- `Qwen3.6-35B` with `PRISM_LM=0`
- `Qwen3.8-27B` with `PRISM_LM=0`
- `Ternary-Bonsai-2-27B` with `PRISM_LM=1`

The comparison was run through the direct llama.cpp router endpoint at `http://localhost:8080/v1`, because that is the active server being selected by the runtime switch in `scripts/entrypoint.llamacpp-router.sh` and the env value in `VERSIONS.env`.

## Benchmark setup

### Runtime switch
The router binary is selected by `PRISM_LM`:

- `PRISM_LM=0` -> stock `/app/llama-server`
- `PRISM_LM=1` -> PrismML `/app/prism-ml/llama-server`

The service was recreated between model runs to ensure the correct binary was active before measuring.

### Router preset settings
The preset defines global defaults shared by all workers:

- `ngl = 99`
- `ctx-size = 131072`
- `threads = 8`
- `parallel = 1`
- `ubatch-size = 1024`
- `cache-type-k = q4_0`
- `cache-type-v = q4_0`

The benchmark models override the prompt batch setting, while their context
setting is inherited from the global section. The effective startup settings
are:

| Setting | Qwen3.6-35B | Qwen3.8-27B | Ternary-Bonsai-2-27B |
|---|---:|---:|---:|
| `ngl` | 99 | 99 | 99 |
| `ctx-size` | 131072 | 131072 | 131072 |
| `threads` | 8 | 8 | 8 |
| `parallel` | 1 | 1 | 1 |
| `batch-size` | 4096 | 4096 | 4096 |
| `ubatch-size` | 1024 | 1024 | 1024 |
| `cache-type-k` | `q4_0` | `q4_0` | `q4_0` |
| `cache-type-v` | `q4_0` | `q4_0` | `q4_0` |

These are worker startup settings and are not changed by OpenAI API requests.
Request-level values such as `max_tokens`, `temperature`, and `top_p` apply to
individual generations. Keeping the effective startup settings identical keeps
the comparison focused on the model and binary choice rather than runtime drift.

### Workload
For each model, we ran:
1. one cold-start run after router recreation
2. four text requests, with the first request treated as warm-up
3. three measured text repeats after warm-up
4. one fixed image-description test using `workspace/data/person.png`

The same prompt and same image were reused across all three model runs.

## Measured results

### Text benchmark (3 repeats after cold start)

| Model | PRISM_LM | Cold start | Repeat mean latency | Prompt eval t/s | Decode/generation t/s | Repeat latency samples |
|---|---:|---:|---:|---:|---:|---|
| Qwen3.6-35B | 0 | 13.841s | 4.202s | 36.444 | 64.389 | 13.807s, 4.124s, 4.182s, 4.301s |
| Qwen3.8-27B | 0 | 13.921s | 7.039s | 16.882 | 39.733 | 15.897s, 7.079s, 6.969s, 7.068s |
| Ternary-Bonsai-2-27B | 1 | 13.854s | 6.617s | 15.203 | 42.862 | 10.793s, 7.045s, 6.392s, 6.415s |

The benchmark captures llama.cpp phase throughput from each response's `timings` object:

| Process type | JSON field | Meaning |
|---|---|---|
| Prompt evaluation | `prompt_per_second` | Input/prompt tokens processed per second |
| Decode / generation | `predicted_per_second` | Output tokens generated per second; stored under both `decode_tokens_per_second` and `generation_tokens_per_second` |
| Speculative draft | `draft_n / draft_ms` | Draft tokens per second when the server reports draft duration; otherwise stored as `null` |

The raw result format stores all requests under `text.results`, marks the first
request as the excluded warm-up, and reports means under
`repeat_mean_tokens_per_second` using only the remaining measured requests.

### Vision benchmark

| Model | PRISM_LM | Vision latency | Result |
|---|---:|---:|---|
| Qwen3.6-35B | 0 | 8901.3ms | Empty response in this run |
| Qwen3.8-27B | 0 | 13942.5ms | Empty response in this run |
| Ternary-Bonsai-2-27B | 1 | 6101.9ms | Non-empty image description returned |

## Findings so far

1. Qwen3.6-35B had the highest measured text decode rate at `64.389 t/s`.
2. Ternary-Bonsai-2-27B had the lowest repeated text latency at `6.617s` in this 8-thread run.
3. Ternary-Bonsai-2-27B was fastest on the image-description benchmark and returned the only non-empty image description.
4. All three text prompts returned empty `message.content` because the `max_tokens=256` budget was consumed by reasoning output; this is a benchmark configuration issue, not evidence of absent model generation.
5. Qwen3.6-35B also exhausted its `max_tokens=512` vision budget in reasoning, while Qwen3.8 and Ternary returned visible image descriptions.

## Interpretation
The current data suggests that Qwen3.6-35B is strongest for raw decode throughput, while Ternary is favorable for latency and multimodal output. The text-quality comparison is not valid until the reasoning budget and output budget are separated in the benchmark.

## Recommended next steps

1. Increase `max_tokens` enough to cover reasoning plus the requested final answer, then rerun quality comparisons.
2. Record median and p95 latency in addition to mean values.
3. Repeat the same benchmark with the same fixed prompt and image at least 3 more times on each model.
4. Re-check the direct router endpoint for every model before each run to confirm the expected alias and binary.
5. Keep `PRISM_LM` and service recreation as a hard requirement between model switches.

## Saving the benchmark data
The raw output currently lives at:

- `benchmarks/llama-router-qwen-vs-ternary-vs-qwen36.json`

This file is the source of truth for the current result set and should be updated whenever the benchmark is rerun.
