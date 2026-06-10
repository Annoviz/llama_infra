# Unsloth service

## Project
- URL: `https://github.com/unslothai/unsloth`
- Description: Optimized fine-tuning and inference stack for transformer models with GPU-first workflows.

## Compose
- File: `compose/main/60-unsloth.yml`
- Service name: `unsloth-server`
- Image: `unsloth/unsloth:${UNSLOTH_VERSION:-2026.5.9-pt2.10.0-vllm-0.16.0-cu12.8-studio-release-v0.1.43-beta-2026-MAY-31}`

## Ports
- `${UNSLOTH_JUPYTER_PORT:-8888}:8888`
- `${UNSLOTH_API_PORT:-8000}:8000`

## Storage and mounts
- `${DATA_DIR:-./data}/unsloth/work:/workspace/work`
- `./workspace:/workspace/project`

## Runtime defaults
- `JUPYTER_PORT=8888`
- `JUPYTER_PASSWORD=${UNSLOTH_JUPYTER_PASSWORD:-change-me}`

## Make targets
- `make config-unsloth`
- `make pull-unsloth`
- `make up-unsloth`
- `make logs-unsloth`
- `make restart-unsloth`
- `make down-unsloth`

## Notes
- Optional service: not started by `make up-main`.
- Included in full start path `make up-main-all`.

## Last verified

- Date: 2026-06-10
- Image tag: `2026.5.9-pt2.10.0-vllm-0.16.0-cu12.8-studio-release-v0.1.43-beta-2026-MAY-31`
- Validated via `make config-unsloth`
