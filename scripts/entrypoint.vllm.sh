#!/usr/bin/env bash
set -euo pipefail

REPO="${VLLM_MODEL_REPO:?MODEL_REPO not set}"
SERVED="${VLLM_SERVED_NAME:?SERVED_NAME not set}"
MAX_LEN="${VLLM_MAX_LEN:-8192}"
GPU_MEM="${VLLM_GPU_MEM:-0.45}"
EXTRA="${VLLM_EXTRA_FLAGS:-}"

echo "[vllm-entrypoint] Ensuring model ${REPO} is cached..."
python3 -c "
from huggingface_hub import scan_cache_dir
cache = scan_cache_dir()
repos = {r.repo_id for r in cache.repos}
target = '${REPO}'
if target not in repos:
    from huggingface_hub import snapshot_download
    print(f'[vllm-entrypoint] Downloading {target}...')
    snapshot_download(repo_id=target, repo_type='model')
    print('[vllm-entrypoint] Download complete.')
else:
    print(f'[vllm-entrypoint] {target} already cached — skipping download.')
"

echo "[vllm-entrypoint] Starting vLLM: ${REPO} as '${SERVED}' (gpu_mem=${GPU_MEM}, max_len=${MAX_LEN})"

exec vllm serve \
    "${REPO}" \
    --port 8000 \
    --max-model-len "${MAX_LEN}" \
    --gpu-memory-utilization "${GPU_MEM}" \
    --served-model-name "${SERVED}" \
    ${EXTRA}
