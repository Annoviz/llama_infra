# Docker MCP Gateway Guide

This document provides instructions for deploying and configuring the Docker MCP Gateway on Linux, specifically for environments running Docker Engine without Docker Desktop.

## Overview
The Docker MCP Gateway is a centralized proxy that orchestrates Model Context Protocol (MCP) servers. Instead of managing multiple individual MCP server installations and ports, the Gateway runs them as isolated Docker containers and handles communication between the AI client and these servers.

### Key Benefits
- **Isolation**: Servers run in restricted containers with controlled network and resource access.
- **Lifecycle Management**: The Gateway starts/stops servers on demand.
- **Centralized Config**: Manage credentials and profiles in one place.
- **Security**: Reduces risks associated with running arbitrary MCP binaries directly on the host.

## Installation
Depending on your environment, choose one of the following methods:

### Option 1: Docker Desktop (Recommended)
If you are using Docker Desktop, the MCP Gateway is integrated into the **MCP Toolkit**.
- **Enablement**: Enable the MCP Toolkit in your Docker Desktop settings.
- **Operation**: The Gateway runs automatically in the background. You can configure servers through the Docker Desktop UI or via the `docker mcp` CLI plugin which comes pre-installed.

### Option 2: Manual Installation (Linux without Docker Desktop)
Since the official toolkit is designed for Docker Desktop, use this manual process for Docker Engine.

#### 1. Install the `docker-mcp` Binary
The gateway is installed as a Docker CLI plugin. You can download the latest binary from the [GitHub Releases page](https://github.com/docker/mcp-gateway/releases).

```bash
# Create the CLI plugins directory if it doesn't exist
mkdir -p ~/.docker/cli-plugins

# Download and install (Example for amd64)
curl -fsSL https://github.com/docker/mcp-gateway/releases/download/v0.41.0/docker-mcp-linux-amd64.tar.gz | tar -xz -C ~/.docker/cli-plugins/

# Ensure the binary is executable
chmod +x ~/.docker/cli-plugins/docker-mcp
```


### 2. The `docker-pass` Workaround (Credential Helper)
The gateway often requires a credential helper to manage secrets securely.

**Install `docker-credential-pass`:**
```bash
# Replace $ARCH with amd64 or arm64
curl -fsSL https://github.com/docker/docker-credential-helpers/releases/download/v0.9.5/docker-credential-pass-v0.9.5.linux-amd64 -o /usr/local/bin/docker-credential-pass
chmod +x /usr/local/bin/docker-credential-pass
```

**Create the wrapper plugin:**
```bash
cat > ~/.docker/cli-plugins/docker-pass << 'EOF'
#!/bin/bash
if [[ "$1" == "docker-cli-plugin-metadata" ]]; then
  echo '{"SchemaVersion":"0.1.0","Vendor":"Docker","Version":"v1.0.0","ShortDescription":"Docker Pass secrets helper"}'
  exit 0
fi
exec docker-credential-pass "$@"
EOF
chmod +x ~/.docker/cli-plugins/docker-pass
```

## Configuration

### Secrets Management
Create a secrets file to store API keys and credentials for your MCP servers.

```bash
mkdir -p ~/.docker/mcp
cat > ~/.docker/mcp/secrets.env << 'EOF'
# Format: server_name.variable=value
duckduckgo.api_key=your-key-here
open-websearch.api_key=your-key-here
EOF
chmod 600 ~/.docker/mcp/secrets.env
```

### Running the Gateway
Start the gateway using a specific transport (SSE is common for remote clients) and port.

```bash
docker mcp gateway run \
  --transport sse \
  --port 8811 \
  --secrets ~/.docker/mcp/secrets.env
```

## Linking to Claude Code

Once the gateway is running, add it as an MCP server in Claude Code:

```bash
claude mcp add docker-mcp-gateway --transport http http://localhost:8811/sse
```

## Troubleshooting
- **Binary 404**: If the latest release URL fails, check the [GitHub Releases](https://github.com/docker/mcp-gateway/releases) page manually for the correct version tag (e.g., `v0.41.0`).
- **Permissions**: Ensure `~/.docker/cli-plugins` is in your PATH or that you are using the `docker mcp ...` command which automatically looks in that directory.
