# Docker MCP Gateway Guide

The Docker MCP Gateway is a centralized proxy that orchestrates Model Context Protocol (MCP) servers. Instead of managing multiple individual MCP server installations and ports, the Gateway runs them as isolated Docker containers and handles communication between the AI client and these servers.

### Key Benefits
- **Isolation**: Servers run in restricted containers with controlled network and resource access.
- **Lifecycle Management**: The Gateway starts/stops servers on demand.
- **Centralized Config**: Manage credentials and profiles in one place.
- **Security**: Reduces risks associated with running arbitrary MCP binaries directly on the host.

## Project Integration

### Compose File Location
- File: `compose/main/70-mcp-gateway.yml`
- Service name: `mcp-gateway`
- Image: `docker/mcp-gateway:${MCP_GATEWAY_VERSION:-v0.43.3}`

### Ports
- `8811:8811` (SSE endpoint)

### Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_GATEWAY_VERSION` | `v0.43.3` | Docker MCP Gateway image tag |
| `MCP_GATEWAY_PORT` | `8811` | Gateway listen port |
| `MCP_TRANSPORT` | `sse` | Transport mode (stdio/sse/streaming) |
| `MCP_PORT` | `8811` | Gateway internal port |
| `MCP_API_KEY` | `` | API key for authentication |
| `MCP_GATEWAY_AUTH_TOKEN` | `` | Bearer token for SSE auth |
| `DOCKER_MCP_ALLOW_INSECURE_REMOTE_URLS` | `0` | Allow insecure remote URLs |

### Dependencies
- Depends on services defined in the compose file (add via `depends_on`)

### Environment Files
- Secrets: `workspace/mcp/secrets.env` (format: `server_name.variable=value`)

## Running the Gateway

### Using Compose
```bash
make up-mcp-gateway
```

### Manual Docker Run
```bash
docker compose -f compose/main/70-mcp-gateway.yml up
```

### Stopping the Gateway
```bash
make down-mcp-gateway
```

## Adding New MCP Services to the Gateway

### Method 1: Using Docker MCP Catalog (Recommended)

The Gateway can automatically discover servers from the official Docker MCP Catalog.

**Step 1: Enable Profiles Feature**
```bash
# Note: docker mcp CLI requires Docker Desktop's MCP Toolkit
# For Linux without Docker Desktop, use Method 2 or 3 instead
docker mcp feature enable profiles
```

**Step 2: Create a Profile**
```bash
# Create a profile with GitHub server
docker mcp profile create --name dev-tools \
  --server catalog://mcp/docker-mcp-catalog/github

# List available profiles
docker mcp profile list
```

**Step 3: Start Gateway with Profile**
```bash
docker compose -f compose/main/70-mcp-gateway.yml up \
  --set mcp-gateway.command="gateway run --transport sse --port 8811 --profile dev-tools"
```

### Method 2: Using Command Line Flags

Specify servers directly in the gateway command.

**Step 1: Update Compose File**
Edit `compose/main/70-mcp-gateway.yml`:
```yaml
services:
  mcp-gateway:
    command: ["gateway run", "--transport", "sse", "--port", "8811", "--servers", "duckduckgo,brave,filesystem"]
```

**Step 2: Restart Gateway**
```bash
make restart-mcp-gateway
```

### Method 3: Using Registry Configuration

The `--registry` flag is used to specify a custom catalog file for **Docker MCP Catalog** servers only. It does NOT work with standalone MCP server images.

**Important:** When using `--servers` or `--profile`, the `--registry` flag is ignored (per official docs).

**Step 1: Create Registry Config**
```bash
cat > workspace/mcp/registry.yaml << 'EOF'
registry:
  duckduckgo:
    ref: ""
  brave:
    ref: ""
  filesystem:
    ref: ""
EOF
```

**Step 2: Update Compose File** (already configured in `compose/main/70-mcp-gateway.yml`)
```yaml
services:
  mcp-gateway:
    volumes:
      - ./workspace/mcp/registry.yaml:/etc/registry.yaml:ro
    command: ["gateway run", "--transport", "sse", "--port", "8811"]
```

**Note:** This only works with catalog servers like `docker/mcp-catalog/github`. For custom MCP servers (Open WebSearch, Brave Search, Gotenberg), use Method 4.

### Method 4: Running Standalone MCP Servers

For servers not in the catalog, pull and run them directly.

**Step 1: Pull MCP Server Image**
```bash
docker pull nickclyde/duckduckgo-mcp-server
```

**Step 2: Add to Compose File**
```yaml
services:
  mcp-gateway:
    command: ["gateway run", "--transport", "sse", "--port", "8811", "--server", "nickclyde/duckduckgo-mcp-server"]
```

### Method 5: Using Docker Compose Include

For complex setups, include additional compose files.

**Step 1: Create Server Compose File**
```yaml
# compose/mcp/servers.yml
services:
  duckduckgo:
    image: nickclyde/duckduckgo-mcp-server
    ports:
      - "8000:8000"
    environment:
      - MCP_TRANSPORT=streamable-http
      - MCP_SERVER_PORT=8000
```

**Step 2: Update Main Compose File**
```yaml
services:
  mcp-gateway:
    command: ["gateway run", "--transport", "sse", "--port", "8811"]
    depends_on:
      - duckduckgo
```

## Supported MCP Server Sources

The Gateway supports MCP servers from:
- Docker MCP Catalog (official servers)
- OCI images (pull from Docker Hub, GHCR, etc.)
- Custom local files
- Remote servers with OAuth authentication

### Official Docker MCP Registry

The official Docker MCP Gateway image is hosted on Docker Hub:

| Image | Registry | Version | Description |
|-------|----------|---------|-------------|
| `docker/mcp-gateway` | `registry-1.docker.io/docker/mcp-gateway` | `v0.43.3` (current) | Official Docker MCP Gateway from Docker Inc. |

The official image is available at: https://hub.docker.com/r/docker/mcp-gateway

### Compatible MCP Registries

The MCP Gateway supports multiple registry sources via the `--registry` flag:

| Registry | URL | Description |
|----------|-----|-------------|
| **Docker MCP Catalog** | `docker-mcp.yaml` (built-in) | Official Docker catalog with GitHub, Git, Filesystem servers |
| **Anthropic MCP Registry** | `https://registry.modelcontextprotocol.io` | Community-owned registry backed by Anthropic, GitHub, Microsoft |
| **agentic-community MCP Gateway & Registry** | Custom config | Enterprise control plane supporting local + imported servers |

### Using External Registries

To use an external registry with the Gateway:

```yaml
services:
  mcp-gateway:
    command: ["gateway run", "--transport", "sse", "--port", "8811", "--registry", "/etc/registry.yaml"]
    volumes:
      - ./workspace/mcp/registry.yaml:/etc/registry.yaml:ro
```

The `registry.yaml` format supports importing servers from external registries:
```yaml
registry:
  # Local servers
  filesystem:
    ref: "anthropics/mcp-filesystem"
  
  # Imported from Anthropic registry
  anthropic-mcp-server:
    ref: "https://registry.modelcontextprotocol.io/v0.1/servers/anthropic-mcp-server"
```

See https://agentic-community.github.io/mcp-gateway-registry/ for full documentation on importing external registries.

### Project MCP Services

Your project includes these MCP services that can be orchestrated through the Gateway:

| Service | Compose File | Image | Port | Purpose |
|---------|--------------|-------|------|---------|
| **MCP Gateway** | `compose/main/70-mcp-gateway.yml` | `docker/mcp-gateway:v0.43.3` | 8811 | Central proxy for all MCP servers |
| **Open WebSearch** | `compose/main/80-duckduckgo-mcp.yml` | `ghcr.io/aas-ee/open-web-search:latest` | 5050 | DuckDuckGo web search (no API key) |
| **Brave Search MCP** | `compose/main/70-open-websearch-mcp.yml` | Custom build | 5051 | Brave Search integration |
| **Gotenberg MCP** | `compose/gotenberg/20-gotenberg-mcp.yml` | Python + Gotenberg | 3015 | PDF generation for web search results |

### Common MCP Servers for AI Agents

| Server | Purpose | Image |
|--------|---------|-------|
| DuckDuckGo Search | Free web search without tracking | `nickclyde/duckduckgo-mcp-server` |
| Brave Search | Web, image, video, news search | `mikechao/brave-search-mcp` |
| GitHub | Repository access, code search | `docker/mcp-catalog/github` |
| Git | Local git operations | `anthropics/mcp-git` |
| Filesystem | Read/write local files | `anthropics/mcp-filesystem` |
| Python | Execute Python code sandboxed | `anthropics/mcp-python` |
| Memory | Database for storing/retrieving data | `anthropics/mcp-memory` |

## Command Line Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--block-network` | Block tools from accessing forbidden network resources | false |
| `--block-secrets` | Block secrets from being/received sent to/from tools | true |
| `--catalog` | Path to the docker-mcp.yaml catalog | `docker-mcp.yaml` |
| `--config` | Path to the config.yaml | `~/.docker/mcp/config.yaml` |
| `--cpus` | CPUs allocated to each MCP Server | 1 |
| `--dry-run` | Start gateway without listening for connections | false |
| `--interceptor` | List of interceptors to use | - |
| `--keep` | Keep stopped containers | false |
| `--log-calls` | Log calls to the tools | true |
| `--memory` | Memory allocated to each MCP Server | 2Gb |
| `--port` | TCP port to listen on | stdio (default) |
| `--registry` | Path to the registry.yaml | `~/.docker/mcp/registry.yaml` |
| `--secrets` | Colon separated paths for secrets lookup | `docker-desktop` |
| `--servers` | Names of servers to enable | - |
| `--tools` | List of tools to enable | - |
| `--transport` | stdio, sse or streaming | stdio (default) |
| `--verbose` | Verbose output | false |
| `--verify-signatures` | Verify signatures of Docker MCP server images | true |
| `--watch` | Watch for changes and reconfigure | true |

## Troubleshooting

- **Feature not available**: Ensure Docker Desktop is installed with MCP Toolkit enabled.
- **WSL2/containerized environments**: Set `DOCKER_MCP_IN_CONTAINER=1` to bypass Desktop feature checks.
- **Profile errors**: Run `docker mcp feature enable profiles` if profile support is not enabled.
- **Server not found**: Verify the server name in the catalog or use `--server` flag for standalone servers.
- **Secret '...' not found**: Ensure key names in `secrets.env` match the `name` field in catalog YAMLs.

## Equivalent MCP Servers for Your Project

### Web Search (replaces direct `WebSearch` calls)

| Service | MCP Server | Image | Notes |
|---------|------------|-------|-------|
| DuckDuckGo | `duckduckgo-mcp-server` | `nickclyde/duckduckgo-mcp-server` | Free, no API key required |
| Brave Search | `brave-search-mcp` | `mikechao/brave-search-mcp` | Requires Brave API key |

### Filesystem Access (for reading/writing files)

| Service | MCP Server | Image | Notes |
|---------|------------|-------|-------|
| Filesystem | `mcp-filesystem` | `anthropics/mcp-filesystem` | Read-only by default |

### Git Operations (for repository access)

| Service | MCP Server | Image | Notes |
|---------|------------|-------|-------|
| Git | `mcp-git` | `anthropics/mcp-git` | Access local git repositories |

### Python Code Execution (sandboxed)

| Service | MCP Server | Image | Notes |
|---------|------------|-------|-------|
| Python | `mcp-python` | `anthropics/mcp-python` | Execute Python code in sandbox |

### Memory/Database Storage

| Service | MCP Server | Image | Notes |
|---------|------------|-------|-------|
| Memory | `mcp-memory` | `anthropics/mcp-memory` | Store/retrieve data for AI agents |
| SQLite | `mcp-sqlite` | `anthropics/mcp-sqlite` | Query local SQLite databases |

## Example: Running Multiple MCP Servers via Gateway

```bash
# Start gateway with multiple servers enabled
docker compose -f compose/main/70-mcp-gateway.yml up \
  --set mcp-gateway.command="gateway run --transport sse --port 8811 --servers duckduckgo,brave,filesystem"
```

Then add to Claude Code:
```bash
claude mcp add mcp-gateway --transport http http://localhost:8811/sse
```
