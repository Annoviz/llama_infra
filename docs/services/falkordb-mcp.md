# FalkorDB MCP service

## Project
- URL: `https://hub.docker.com/r/falkordb/mcpserver`
- Description: Model Context Protocol server that exposes FalkorDB operations to MCP clients.

## Compose
- File: `compose/main/50-falkordb-mcp.yml`
- Service name: `falkordb-mcpserver`
- Image: `falkordb/mcpserver:${FALKORDB_MCP_VERSION:-1.2.2}`

## Ports
- `3005:3000` (HTTP transport default)

## Dependencies
- Depends on healthy `falkordb`.

## Runtime defaults
- `MCP_TRANSPORT=http`
- `FALKORDB_MCP_PORT=3005`
- Optional: `MCP_API_KEY`

## Make targets
- `make up-falkordb-mcp`
- `make logs-falkordb-mcp`
- `make restart-falkordb-mcp`
- `make down-falkor`
