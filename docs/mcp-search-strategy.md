# MCP Search & Infrastructure Strategy

This document outlines the evaluation of web search MCP implementations and the proposed transition to a unified gateway architecture for `llama_infra`.

## Overview
When routing Claude Code through local servers (e.g., `llama-server`), the built-in server-side web search fails because the local provider lacks Anthropic's backend infrastructure. To restore search capabilities, we must implement a **Model Context Protocol (MCP)** server that handles internet queries locally on the host machine.

## Comparison of Search Approaches

| Approach | Implementation / Image | Pros | Cons | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **Multi-Engine** | `ghcr.io/aas-ee/open-web-search` | Redundancy (Google, Bing, DDG) | Higher latency; potential for "hanging" on one engine | Verified |
| **Dedicated DDG** | `mcp/duckduckgo` or `nickclyde/duckduckgo-mcp-server` | Lightweight, no API keys required, optimized for DDG | stdio-only; cannot be deployed as standalone HTTP container | Incompatible (Standalone) |
| **API-Based** | Brave Search / Google Custom Search | Extremely reliable; official APIs | Requires API keys; potential costs | Fallback Option |

### Recommended DuckDuckGo Images
- **`mcp/duckduckgo`**: Docker Hub Verified, most popular community image.
- **`ashdev/duckduckgo-mcp-server`**: Lightweight Node.js implementation.
- **`ghcr.io/nickclyde/duckduckgo-mcp-server`**: Robust Python-based server.

## Implementation Guides

### 1. Multi-Engine Search (`open-websearch`)
**Deployment (Docker):**
```bash
docker run -d \
  --name open-websearch-mcp \
  --restart unless-stopped \
  -p 127.0.0.1:5050:3000 \
  ghcr.io/aas-ee/open-web-search:latest
```

**Claude Code Configuration:**
```bash
claude mcp add --transport http open-websearch http://localhost:5050/mcp
```
    ``
### 2. Dedicated DuckDuckGo Search (Python Implementation)
Note: Avoid `npm install` for the `@nickclyde` server as it is a Python package.

**Correct Dockerfile:**
```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir duckduckgo-mcp-server
EXPOSE 3000
CMD ["python", "-m", "duckduckgo_mcp_server"]
```

**Claude Code Configuration:**
```bash
claude mcp add duckduckgo-search --scope user -- npx -y @nickclyde/duckduckgo-mcp-server
```

### 3. API-Based Search (Brave / Google)
Requires API keys from the respective provider consoles.

**Google Search Setup:**
```bash
claude mcp add google-search --scope user -- npx -y @modelcontextprotocol/server-google-search --api-key="YOUR_KEY" --cx="YOUR_CX_ID"
```

**Brave Search Setup:**
Add to `~/.claude.json`:
```json
"brave-search": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-brave-search"],
  "env": { "BRAVE_API_KEY": "YOUR_KEY" }
}
```

## Architectural Evolution: Docker MCP Gateway

To avoid "port hell" (managing multiple `5050`, `5051` ports) and improve management, the project is transitioning to a **Unified Gateway Pattern**.

### The Gateway Architecture
Instead of mapping host ports for every service, we deploy a single **MCP Gateway** container that mounts `/var/run/docker.sock`.

- **Mechanism**: Spawns MCP servers as sibling containers and communicates via `stdio` over the Docker socket.
- **Benefit**: Zero host ports exposed for individual MCPs; one single endpoint for Claude Code.

### Installation (Docker Engine / Ubuntu)
1. **Install CLI Plugin:**
   ```bash
   mkdir -p "$HOME/.docker/cli-plugins/"
   curl -L https://github.com/docker/mcp-gateway/releases/latest/download/docker-mcp-linux-amd64 -o "$HOME/.docker/cli-plugins/docker-mcp"
   chmod +x "$HOME/.docker/cli-plugins/docker-mcp"
   ```
2. **Configure Registry (`~/.docker/mcp/registry.yaml`):**
   ```yaml
   registry:
     open-websearch:
       image: ghcr.io/aas-ee/open-web-search:latest
   ```
3. **Link to Claude:**
   ```json
   "docker-mcp-gateway": {
     "command": "docker",
     "args": ["mcp", "gateway", "run"]
   }
   ```

## Troubleshooting & FAQs

### Issue: "Did 0 searches" or empty results
**Cause**: Usually occurs when routing through a local `llama-server` without an MCP provider. The built-in search tool is server-side (Anthropic) and cannot be executed by a local LLM engine.
**Fix**: Install one of the MCP servers listed in the Implementation Guides above.

### Issue: Docker Build Failure for DDG MCP
**Cause**: Attempting to use `npm install` on a Python package.
**Fix**: Use the Python-based Dockerfile provided in the "Dedicated DuckDuckGo Search" section.

## Success Criteria
- [x] Successful web search return in < 5 seconds.
- [ ] Zero port conflicts between multiple MCP services.
- [ ] Unified configuration management for all AI tools via Gateway.
