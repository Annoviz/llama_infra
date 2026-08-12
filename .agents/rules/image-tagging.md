# Image Tagging Conventions

## Rule

When working with Docker images that use `latest` tags or fixed branch-like tags (e.g., `full-cuda13`), always tag them with their creation date before use. This ensures reproducibility and traceability of which image version is running.

## Date Tag Format

Append the image creation date in `YYYY-MM-DD` format to the existing tag:

- **latest** → replace with `<date>` (e.g., `ghcr.io/aas-ee/open-web-search:v2.1.11`)
- **fixed tags** → append date (e.g., `full-cuda13` → `full-cuda13-2026-07-20`)

## Workflow

### When pulling a new image:

```bash
# 1. Pull the image
docker pull ghcr.io/ggml-org/llama.cpp:full-cuda13

# 2. Inspect to get creation date
CREATED=$(docker inspect ghcr.io/ggml-org/llama.cpp:full-cuda13 --format '{{.Created}}' | cut -dT -f1)

# 3. Tag with date
docker tag ghcr.io/ggml-org/llama.cpp:full-cuda13 "ghcr.io/ggml-org/llama.cpp:full-cuda13-${CREATED}"
```

### When updating compose files:

- Prefer pinned version tags over `latest` (e.g., `v2.1.11` instead of `latest`)
- If no versioned tag exists, use the date-tagged image in compose files
- Always run `docker images <repo>` to check existing date tags before pulling new ones

### Existing images:

When adding a new rule or updating infra, scan for untagged images and apply date tags:

```bash
for img in $(docker images ghcr.io/ggml-org/llama.cpp --format '{{.Repository}}:{{.Tag}}'); do
  repo=$(echo "$img" | cut -d: -f1)
  tag=$(echo "$img" | cut -d: -f2)
  created=$(docker inspect "$img" --format '{{.Created}}' | cut -dT -f1)
  docker tag "$img" "${repo}:${tag}-${created}"
done
```

## Exceptions

- Images with explicit version pins (e.g., `v0.32.6`, `v2.1.11`) do not need date tags — the version is sufficient for reproducibility
- CI/CD pipelines may use `latest` if they pull fresh on each run, but production compose files must use pinned or date-tagged images
