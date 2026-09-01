# Rule: WebSearch via open-websearch MCP Fallback

Use the native `WebSearch` tool first. Fall back to the `open-websearch-mcp` MCP tools in any of these cases:

1. User explicitly asks for open-websearch (e.g. "use openwebsearch", "search via MCP").
2. Native `WebSearch` **fails** (error, timeout, HTTP non-2xx status).
3. Native `WebSearch` returns **zero / empty results**.

If the MCP server is unavailable, fall back to native `WebSearch` — the failure must be transparent, never a hard dependency.

## Why

The project runs its own multi-engine search stack (`open-websearch-mcp`, see `compose/main/70-open-websearch-mcp.yml`). When it is up:
- results stay consistent with the configured engine/domain settings,
- DuckDuckGo-side failures or rate-limits are covered by other engines inside that stack,
- searches respect project domain filtering.

## Endpoint

`http://localhost:${OPEN_WEBSEARCH_PORT:-5050}/mcp` (service `open-websearch-mcp`, port mapped in the compose file).

## How to Apply

```
WebSearch(query) ── fail / error ────────────▶ open-websearch MCP search
      │                                          (same query, retry once)
      ├── 0 / empty results ──────────────────▶ open-websearch MCP search
      └── explicit user request ──────────────▶ open-websearch MCP search (skip native)
```

One MCP retry attempt per query is enough; if that also fails, report the retrieval failure and continue with available local knowledge — do not loop between tools.

## Verification

Before relying on the MCP path, confirm the service is up:

```bash
make ps-all | grep open-websearch-mcp   # "running" status expected
```

or check `$OPEN_WEBSEARCH_PORT` in `.env` (default 5050) and probe `http://localhost:<port>/mcp`.
