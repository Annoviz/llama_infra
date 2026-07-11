---
name: vision-test
description: Test multimodal image understanding of a local Ollama model with timing and token stats
---

# Skill: Vision Test

Test multimodal (image understanding) capability of a local Ollama model by sending an image + prompt via `/api/chat` and displaying the response with timing info.

## Purpose

Send an image + prompt to a local Ollama model via `/api/chat` and display the response with timing info, verifying whether a model can understand visual input.

## Command

```bash
make vision-test MODEL=<name> IMAGE=<path> PROMPT="<text>" MAX_TOKENS=512 OLLAMA_BASE_URL=http://localhost:11434 TIMEOUT=300
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `MODEL` | Ollama model name (e.g. `fast-coder`, `planner`, `llava`) | `fast-coder` |
| `IMAGE` | Path to image file (PNG, JPG, WEBP, GIF) | required |
| `PROMPT` | Prompt sent alongside the image | `"Describe this image in detail."` |
| `MAX_TOKENS` | Max output tokens | `512` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |
| `TIMEOUT` | Request timeout (seconds) | `300` |

## Available Images

| Image | Path | Description |
|-------|------|-------------|
| Person portrait | `workspace/data/person.png` | RBG illustration |
| Dog park | `workspace/data/DOG_PARK-3-1024x576.jpg` | Outdoor scene with dogs |
| Compare chart | `workspace/data/deepseek-r1-compare.jpg` | Screenshot/chart |
| Street photo | `workspace/data/11-19-strotterdam__01.jpg` | Urban street scene |

## Examples

```bash
# Quick test with a known multimodal model (baseline)
make vision-test MODEL=llava IMAGE=workspace/data/person.png PROMPT="Describe this image." MAX_TOKENS=256 OLLAMA_BASE_URL=http://localhost:11434 TIMEOUT=300

# Test fast-coder after rebuilding with mmproj
make vision-test MODEL=fast-coder IMAGE=workspace/data/DOG_PARK-3-1024x576.jpg PROMPT="What animals are in this image and what are they doing?" MAX_TOKENS=256 OLLAMA_BASE_URL=http://localhost:11434 TIMEOUT=300

# Test planner with a chart
make vision-test MODEL=planner IMAGE=workspace/data/deepseek-r1-compare.jpg PROMPT="What does this chart show?" MAX_TOKENS=512 OLLAMA_BASE_URL=http://localhost:11434 TIMEOUT=300
```

## Output

The script prints:
- **Model** name and image path
- **Time** — total wall-clock ms for the response
- **Eval tokens** — output token count from Ollama
- **Response text** — the model's answer

An empty response means the model either lacks vision capabilities or hasn't been rebuilt with an mmproj (multimodal projector) blob.

## Notes

- If a model returns nothing, rebuild it first: `ollama create <model> -f workspace/models/<Model>.Modelfile`
- The Modelfile must include both the base GGUF and the `mmproj-BF16.gguf` line for vision to work.
- Script lives at `scripts/vision_test.py`.
