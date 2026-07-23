# Open Web Search MCP service

Multi-engine web search MCP server that allows Claude to perform internet queries via Google, Bing, and DuckDuckGo without requiring individual API keys.

## Compose
- File: `compose/main/70-open-websearch-mcp.yml`
- Service name: `open-websearch-mcp`
- Image: `ghcr.io/aas-ee/open-web-search:latest`

## Ports
- `${OPEN_WEBSEARCH_PORT:-5050}:3000` (MCP HTTP/SSE endpoint)

## Dependencies
- None.

## Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `OPEN_WEBSEARCH_PORT` | 5050 | Host port for the MCP server |

## Make Targets
- `make up-open-websearch-mcp`
- `make down-open-websearch-mcp`
- `make restart-open-websearch-mcp`
- `make logs-open-websearch-mcp`
- `make ps-open-websearch-mcp`

## Notes
- This service provides a bridge for Claude Code to access the web. 
- To connect Claude Code CLI, use: `claude mcp add --transport http open-websearch http://localhost:5050/mcp`
