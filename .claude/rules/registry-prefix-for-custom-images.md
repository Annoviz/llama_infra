# Rule: Use ${REGISTRY:-...} for Custom-Built Images

Custom-built Docker images should use `${REGISTRY:-fallback}` prefix to push to the user's registry.

## Why

Bare local tags (`llama-infra-vllm:v0.25.0`) don't push to `dk-server:5000` or any remote registry. The project uses `REGISTRY=dk-server:5000` in `.env`.

## How to Apply

Follow the pattern from `compose/llama/20-llamacpp-py.yml`:
```yaml
image: ${REGISTRY:-fallback-name}/<service>:${VERSION}
```

This pushes to user's registry when set, falls back to local tag otherwise. Always check existing compose files for precedent before adding new custom images.
