# Rule: Validate Compose Config Before Deploying Multi-File Stacks

When making changes across multiple compose files (networks, services, env), validate the assembled config before deploying.

## Why

Multi-file stacks (`docker compose -f file1.yml -f file2.yml ...`) can have subtle conflicts — duplicate service names, incompatible network references, volume path issues — that only surface at assemble time, not when editing individual files. Deploying a broken stack wastes container restarts and health check retries.

## How to Apply

After any compose change:
```bash
docker compose --project-directory $(CURDIR) -f compose/llama/05-*.yml -f compose/llama/15-*.yml -f compose/llama/25-*.yml config 2>&1 | tail -5
```

Or use the existing Makefile target if one covers the stack. If no target exists, add one (see workflow suggestion).
