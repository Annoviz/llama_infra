# Qwen3.8-27B

Compact dense vision-language model from the Qwen open-model family. Native image and video understanding, flexible thinking control (on by default, `reasoning_effort` tunable, historical reasoning retained via `preserve_thinking`). Optimized for coding, professional work, and long-horizon agentic tasks.

- Source: [unsloth/Qwen3.8-27B-GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) (base: `Qwen/Qwen3.8-27B`)
- License: Apache-2.0
- Architecture: `qwen35`, 27B params, causal LM + vision encoder with MTP (multi-token prediction) for fast inference

## Architecture highlights

| Spec | Value |
|------|-------|
| Layers | 64 — layout `16 × (3 × (Gated DeltaNet → FFN) → 1 × (Gated Attention → FFN))` |
| Hidden dim | 5120 |
| Gated DeltaNet (linear attn) | 48 V heads / 16 QK heads, head dim 128 |
| Gated Attention | 24 Q heads / 4 KV heads, head dim 256, RoPE dim 64 |
| FFN intermediate | 17,408 |
| Vocab (padded) | 248,320 |
| Context | 262,144 native; extensible to ~1M via YaRN |

The hybrid DeltaNet/attention layout gives sub-quadratic scaling for long contexts.

## Quantizations (Unsloth Dynamic V3.0 preview)

Recommended: **UD-Q4_K_XL (~17.9 GB)** — SOTA quality/size balance, default tag in llama.cpp/Ollama examples.

| Bits | Options (size) |
|------|----------------|
| 2-bit | UD-IQ2_XXS 9.01 GB · UD-IQ2_M 10.3 GB · UD-Q2_K_XL 10.7 GB |
| 3-bit | UD-IQ3_XXS 11.9 GB · Q3_K_S 12.6 GB · Q3_K_M 13.8 GB · UD-Q3_K_XL 13.4 GB |
| 4-bit | IQ4_XS 15.7 GB · Q4_K_S 16.1 GB · IQ4_NL 16.3 GB · Q4_0 16.1 GB · Q4_1 17.5 GB · Q4_K_M 17.1 GB · UD-Q4_K_XL 17.9 GB |
| 5-bit | Q5_K_S 19.3 GB · Q5_K_M 19.8 GB · UD-Q5_K_XL 20.2 GB |
| 6-bit | Q6_K 22.9 GB · UD-Q6_K_XL 25.9 GB |
| 8-bit | Q8_0 29 GB · UD-Q8_K_XL 31.5 GB |
| 16-bit | BF16 54.7 GB |

VRAM note: on the single-GPU llama.cpp stack (48 GB RTX 6000 Ada), Q4-KXL leaves ~28 GB for KV cache — comfortable at 128K+ context; Q5/Q6 get tight beyond that.

## Recommended sampling

| Mode | temperature | top_p | top_k | presence_penalty |
|------|-------------|-------|-------|------------------|
| Thinking (default) | 1.0 | 0.95 | 20 | 0.0 |
| Instruct (non-thinking) | 0.7 | 0.80 | 20 | 1.5 |

For agentic tasks give the model headroom: up to 262,144 tokens for reasoning content + 131,072 for final response (within 1M context). Long videos: set video preprocessor `longest_edge` to 469,762,048 (~224k video tokens) for hour-scale inputs.

## Using it here

```bash
# llama.cpp stack (GPU-native) — download GGUF into ${MODELS}, reference as /models/...
llama-server -hf unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL

# or via the Ollama-based main stack
ollama run hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL
```

Model config (if added) goes in `workspace/models/qwen3.8-27b-config.json` with required fields `model`, `model_alias`, `chat_format` and the `/models/...` path convention. Multimodal: vision + video supported, no separate mmproj needed (vision encoder is built into the GGUF).
