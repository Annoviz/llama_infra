#!/bin/bash

VLLM_MODEL_REPO=${1:-${VLLM_MODEL_REPO:-"hf://Qwen/Qwen3.6-35B-A3B-FP8"}}
hf download "${VLLM_MODEL_REPO}" --repo-type model