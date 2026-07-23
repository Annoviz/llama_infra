# you asked

CopiedCopyEdithow to configure correctly open-web-search docker?

---

# googlesearch response


To correctly configure the **[aas-ee/open-webSearch](https://github.com/aas-ee/open-websearch)** Docker setup, your AI agent needs to deployment-configure it as a self-hosted **Model Context Protocol (MCP)** server. This image exposes a streamable HTTP or SSE service that provides AI agents with multi-engine web searching capabilities without needing API keys.

Here are the direct configuration instructions for an agent to execute.

1\. The Core Docker Compose File

Your agent should use this baseline `docker-compose.yml` to correctly spin up the service:

```yaml
version: "3.8"

services:
  web-search:
    image: ghcr.io/aas-ee/open-web-search:latest
    container_name: web-search
    working_dir: /app
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - PORT=3000
      # Engine configuration: 'bing' | 'duckduckgo' | 'exa' | 'brave' | 'startpage'
      - DEFAULT_SEARCH_ENGINE=duckduckgo
      # CORS setup required for external web-based AI clients to securely access it
      - ENABLE_CORS=true
      - CORS_ORIGIN=*
      # Optional Proxy configuration if scraping from a restricted network
      # - USE_PROXY=true
      # - PROXY_URL=http://host.docker.internal:7890
    command: ["node", "build/index.js"]
```

Use code with caution.

2\. Connect the Agent's Client Config

Once the Docker container is up and running on port 3000, your agent must configure its respective host platform config file (e.g., Claude Desktop, Cursor, or Cherry Studio).

Option A: Streamable HTTP Protocol (Recommended for Claude Dev / Cline / Cherry Studio)

```json
{
  "mcpServers": {
    "web-search": {
      "type": "streamableHttp",
      "url": "http://localhost:3000/mcp"
    }
  }
}
```

Use code with caution.

Option B: Server-Sent Events (SSE) Protocol Alternative

```json
{
  "mcpServers": {
    "web-search": {
      "type": "sse",
      "url": "http://localhost:3000/sse"
    }
  }
}
```

Use code with caution.

3\. Verification Commands for the Agent

Your agent can run these checks directly against the running container to ensure it is configured cleanly:

-   **Check Service Readiness:** Verify the HTTP entry point responds with a standard health check or protocol schema header.

-   **Test Local One-Shot Scraping:** If inside the application stack workspace, your agent can manually invoke `open-websearch status --json` or query the local endpoint to make sure routing works without rate limits.

Would you like me to show your agent how to:

Route this through a local proxy chain like Clash or V2RayChange the underlying search engine mapping from DuckDuckGo to StartpageConfigure the equivalent runtime setup using pure `docker run` flags instead of Compose

Share

More