# you asked

CopiedCopyEditopen-websearch mcp docker claude add

---

# googlesearch response

To connect the [Aas-ee/open-webSearch](https://github.com/aas-ee/open-websearch) multi-engine MCP server to Claude using Docker, you need to **run the container as a background service and map its HTTP/SSE endpoint** inside your Claude configuration file.

Here is the step-by-step process to deploy and add it.

Step 1: Run Open-WebSearch with Docker

Execute the following command in your terminal to start the background container on port `3000`:

```bash
docker run -d -p 3000:3000 ghcr.io/aas-ee/open-web-search:latest
```

Use code with caution.

Step 2: Add to Claude Configuration

You can link this running container to either **Claude Desktop** or **Claude Code**. Find your specific client config below:

Option A: Claude Desktop

1.  Open your `claude_desktop_config.json` file:
    -   **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
    -   **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
2.  Insert the **streamableHttp** or **sse** configuration under the `mcpServers` object:

```json
{
  "mcpServers": {
    "open-websearch": {
      "type": "streamableHttp",
      "url": "http://localhost:3000/mcp"
    }
  }
}
```

Use code with caution.

Option B: Claude Code (Terminal)

If you are using the terminal-based **Claude Code** agent, run the following command directly in your command line to install the tool globally:

```bash
claude mcp add open-websearch http://localhost:3000/mcp
```

Use code with caution.

_(Alternatively, check your current connected servers using `claude mcp list`.)_

Alternative: Docker MCP Toolkit (GUI)

If you prefer a visual setup without editing files, you can use the [Docker MCP Toolkit](https://docs.docker.com/ai/mcp-catalog-and-toolkit/toolkit/) built directly into Docker Desktop:

1.  Open **Docker Desktop** and navigate to the **MCP Toolkit** extension in the sidebar.
2.  Search for `open-websearch` or browse the web category.
3.  Click **Add MCP Server** to automatically configure it.

Would you like help setting up an **HTTP proxy configuration** if you are on a restricted corporate network, or do you need help **testing the search tool** once added?

Share

More

When you use the **Docker MCP Toolkit**, port conflicts are entirely avoided because **the individual MCP server containers do not publish ports to your host machine**.

The architecture manages network boundaries through a unified routing system:

1\. The Single Gateway Architecture

Instead of every individual MCP server (like Open-WebSearch, GitHub, or Postgres) claiming a port on your machine (e.g., `localhost:3000`, `localhost:3001`), Docker runs a single centralized entry point called the **MCP Gateway**.

-   Only the **MCP Gateway** talks to your host machine or your Claude Desktop client.

-   Your LLM client (Claude) establishes a single connection to this gateway.

2\. Internal Docker Networking

When you click "Add" on a server in the Docker MCP Catalog, Docker spawns that container inside an **isolated internal virtual network**.

-   The containers communicate with the Gateway internally using standard Docker inter-container networking.

-   Since the `-p` (port publish) flag is not used for individual servers, they never bind to your actual computer's physical ports. You could run 10 different MCP servers that all internally use port `3000`, and they will never collide.

3\. Dynamic Stdio / Process Spawning

For many local tools managed by the toolkit, Docker avoids network ports entirely by using **stdio (Standard Input/Output) over a secure Docker socket bridge**. When Claude requests a tool, the toolkit communicates with the container via stream protocols instead of open web ports, preventing local port sniffing or binding exceptions.

* * *

Would you like to know how to **link Claude Desktop to the unified Docker Gateway**, or do you need assistance checking if any existing local services are blocking the default Docker Desktop ports?

Share

More

On **Ubuntu 24.04**, the port-conflict rule behaves exactly the same way, but there is an important Linux architectural detail you should know: **the Docker MCP Toolkit requires Docker Desktop for Linux**. Standard `docker-ce` (Docker Engine) does not natively include the graphical extension toolkit.

If you are running **Docker Desktop** on your Ubuntu machine, port conflicts are completely prevented due to how network bridging operates:

1\. No Ports are Exposed to `localhost`

When you add an MCP server (like Open-WebSearch) via the Toolkit interface, Docker runs the container _without_ publishing ports to your host system.

-   Normal Docker containers use `-p 3000:3000` to bind to your physical machine.

-   Toolkit containers **do not use port publishing**. They remain hidden inside an internal, isolated virtual Docker network bridge.

2\. Internal Network Overlapping is Allowed

Because each MCP server lives inside its own sandboxed virtual container, they are entirely decoupled from each other. You could spawn five different MCP containers that all listen on port `3000` internally, and **they will never conflict** because they do not share the same network namespace or IP address.

3\. Claude Communicates via `stdio` Pipe (No Web Ports)

When you link Claude to the Docker MCP Toolkit, Claude doesn't actually use a web browser address (like `http://localhost:3000`). Instead, it uses standard process inputs and outputs (`stdio`) to pipe instructions straight through the Docker CLI.

Your Claude configuration file (`claude_desktop_config.json`) tells Claude to invoke the Docker client wrapper directly:

```json
{
  "mcpServers": {
    "docker-mcp-gateway": {
      "command": "docker",
      "args": ["mcp", "gateway", "run"]
    }
  }
}
```

Use code with caution.

When Claude boots up, it executes that local command. The `docker mcp` plugin acts as a single router—passing messages back and forth through standard text streams without binding to a single network port on your Ubuntu host.

* * *

Would you like assistance **installing the Docker Desktop package** on Ubuntu 24.04, or would you prefer a **pure Docker Engine setup** using standard port mappings instead of the Toolkit?

Share

More

On a pure **Docker Engine (`docker-ce`) setup** without Docker Desktop, you lose the automatic UI integration, meaning you must **manually control the ports and network binding**.

To use `open-websearch` securely on Ubuntu 24.04 without port conflicts, choose one of the following production setups:

Setup 1: Manual Port Binding (Easiest)

If you are only running one instance of Open-WebSearch, explicitly bind it to a high, unused local port (like `5050`) so it doesn't conflict with other default applications on your host machine.

1.  **Launch the Container:**

    bash

    ```
    docker run -d \
      --name open-websearch-mcp \
      --restart unless-stopped \
      -p 127.0.0.1:5050:3000 \
      ghcr.io/aas-ee/open-web-search:latest
    ```

    Use code with caution.

    _(Note: Using `127.0.0.1:5050:3000` restricts the port strictly to your local machine, keeping it hidden from the open internet.)_
2.  **Add to Claude Desktop (`claude_desktop_config.json`):**

    json

    ```
    {
      "mcpServers": {
        "open-websearch": {
          "type": "streamableHttp",
          "url": "http://127.0.0"
        }
      }
    }
    ```

    Use code with caution.

* * *

Setup 2: The Open-Source Docker CLI Gateway (Best for Multi-MCP)

If you plan to run multiple MCP containers on standard Docker Engine, you can implement the exact same port-free environment as the toolkit by using the [Docker open-source MCP CLI plugin](https://github.com/docker/mcp-gateway). This eliminates host port bindings entirely.

1.  **Install the CLI plugin** manually on Ubuntu:

    bash

    ```
    mkdir -p "$HOME/.docker/cli-plugins/"
    # Download the latest binary for linux-amd64 from the official releases
    curl -L https://github.com -o "$HOME/.docker/cli-plugins/docker-mcp"
    chmod +x "$HOME/.docker/cli-plugins/docker-mcp"
    ```

    Use code with caution.

2.  **Configure your Registry File:**
    Create a local YAML file defining the servers you want to run:

    bash

    ```
    mkdir -p ~/.docker/mcp/
    cat > ~/.docker/mcp/registry.yaml << 'EOF'
    registry:
      open-websearch:
        image: ghcr.io/aas-ee/open-web-search:latest
    EOF
    ```

    Use code with caution.

3.  **Add to Claude Configuration:**
    Point Claude directly to the newly installed Docker CLI command. Claude will talk via standard Unix processes (`stdio`) instead of using network sockets:

    json

    ```
    {
      "mcpServers": {
        "docker-mcp-gateway": {
          "command": "docker",
          "args": ["mcp", "gateway", "run"]
        }
      }
    }
    ```

    Use code with caution.

* * *

Verification

To check if any service on your Ubuntu system is already conflicting or squatting on a specific port before running your containers, execute this network verification command:

```bash
sudo ss -tulpn | grep :3000
```

Use code with caution.

If the command returns blank, port `3000` is completely free to use.

Would you like assistance in:

Writing a **Docker Compose file** to bundle multiple MCP servers together?Troubleshooting file permissions for the **Claude configuration** on Ubuntu 24.04?

Share

More

To connect your pure Docker Engine setup of `open-websearch` directly to the **Claude Code CLI** on Ubuntu 24.04, you can skip configuration files and register it instantly using the command line.

Here is how to run the container and add it seamlessly using the specific `claude mcp` syntax.

Step 1: Run the Docker Container Locally

Run the container on a custom, non-conflicting host port (such as `5050`) restricted to your local loopback interface (`127.0.0.1`):

```bash
docker run -d \
  --name open-websearch-mcp \
  --restart unless-stopped \
  -p 127.0.0.1:5050:3000 \
  ghcr.io/aas-ee/open-web-search:latest
```

Use code with caution.

Step 2: Add it to Claude Code CLI

Claude Code requires you to specify the transport type (`http`) explicitly when running a remote or web-mapped server. Execute this command in your terminal to link it globally:

```bash
claude mcp add --transport http open-websearch http://127.0.0
```

Use code with caution.

Step 3: Verify the Connection

1.  Launch your Claude Code interactive session:

    bash

    ```
    claude
    ```

    Use code with caution.

2.  Run the internal command inside the chat interface to verify that the tool is listed and active:

    text

    ```
    /mcp
    ```

    Use code with caution.

3.  Test it with a query to ensure it leverages the web search container:

    text

    ```
    Use open-websearch to find the latest news about Linux kernel updates.
    ```

    Use code with caution.

Would you like to know how to restrict this MCP server to a **specific project repository** (`--scope project`) instead of applying it globally across your system?

Share

More

The error occurs because **`@nickclyde/duckduckgo-mcp-server` is written in Python, not Node.js (npm)**.

You are getting an exit code 1 because the package does not exist on the global npm registry. It is hosted on [PyPI](https://pypi.org/project/duckduckgo-mcp-server/) and must be installed via Python package managers like `pip` or `uv`.

The Solution

Replace the Node.js/npm configuration in your Dockerfile with a Python environment setup.

Option 1: Using `uv` (Recommended & Fastest)

The official package repository recommends using `uv` or `uvx`.

```dockerfile
FROM python:3.11-slim

# Install uv to manage the package efficiently
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install the duckduckgo mcp server globally/in environment
RUN uv pip install --system duckduckgo-mcp-server

# Expose the port your server listens on (if configured for HTTP/SSE)
EXPOSE 3000

# Run the server
CMD ["uvx", "duckduckgo-mcp-server"]
```

Use code with caution.

Option 2: Using standard `pip`

If you prefer a standard Python setup without extra tools:

```dockerfile
FROM python:3.11-slim

# Install dependencies and the mcp server via pip
RUN pip install --no-cache-dir duckduckgo-mcp-server

# Expose the port your server listens on
EXPOSE 3000

# Run the server
CMD ["python", "-m", "duckduckgo_mcp_server"]
```

Use code with caution.

Why it failed

1.  **Wrong Package Registry:** Running `npm install` searches the Node package ecosystem, where this specific library isn't registered.
2.  **Underlying Runtime:** The server relies on Python components like `httpx` or `curl_cffi` to function.

If you're using this with an **MCP client** like Claude Desktop or Cursor, let me know so I can help you write the correct JSON tool configuration block.

Share

More

No, there is **no official image published by DuckDuckGo itself**, but there are highly trusted, verified, and community-maintained Docker options available.

Because DuckDuckGo does not require an API key to scrape search results, the community has built and standardized several lightweight Model Context Protocol (MCP) containers.

Recommended Docker Options

-   **`mcp/duckduckgo` (Docker Hub Verified):** This is the most popular, trusted community-maintained image with over 500,000 downloads. It is officially recognized and indexed within the [Docker Hub MCP ](https://hub.docker.com/u/mcp).

-   **`ashdev/duckduckgo-mcp-server`:** Another highly popular, lightweight Node.js implementation frequently cited in AI engineer deployment playbooks.

-   **`ghcr.io/nickclyde/duckduckgo-mcp-server`:** A robust, multi-architecture (`linux/amd64` and `linux/arm64`) Python-based server hosted directly on GitHub Packages.

* * *

Easiest Way to Deploy: Docker MCP Toolkit

If you are using Docker Desktop, you do not need to manually configure the Docker commands. Docker includes a built-in **MCP Toolkit & Catalog** that containerizes it automatically:

1.  Open **Docker Desktop** and navigate to the **MCP Catalog** tab.
2.  Search for **DuckDuckGo**.
3.  Click the **\+ Add** button. Docker will securely pull the correct image, isolate it in a sandbox container, and handle the background hosting for you.

* * *

Manual Setup (Claude Desktop Example)

If you prefer to configure your client manually using a standard Docker command, you can insert the container definition directly into your client's configuration file (such as `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "duckduckgo-search": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "mcp/duckduckgo"
      ]
    }
  }
}
```

Use code with caution.

If you want to proceed, let me know:

-   What **AI client or IDE** are you trying to connect this to? (e.g., Claude Desktop, Cursor, VS Code)

-   Do you prefer a **Python-based** or **Node.js-based** backend for your tools?

I can provide the exact configuration snippet for your environment.

Share

More

The error `Request failed with status code 301` means **Bing is detecting your Docker container as a bot** and redirecting it to a verification page. Because the default engine in [Aas-ee/open-websearch](https://github.com/aas-ee/open-websearch) is configured to Bing, it fails immediately.

You can change the fallback flow, switch engines, or fix the Bing block using Docker environment variables.

1\. Change the Default Engine Globally

To completely bypass Bing and use a more resilient engine like **DuckDuckGo** or **Brave** as your primary search engine, pass the `DEFAULT_SEARCH_ENGINE` environment variable when starting your container.

Stop your old container and run it with this configuration:

```bash
docker run -d \
  --name open-websearch-mcp \
  --restart unless-stopped \
  -e DEFAULT_SEARCH_ENGINE=duckduckgo \
  -p 127.0.0.1:5050:3000 \
  ghcr.io/aas-ee/open-web-search:latest
```

Use code with caution.

_(Supported values include `duckduckgo`, `brave`, `exa`, `startpage`, or `baidu`.)_

2\. Instruct Claude to Call Specific Engines Explicitly

The Open-WebSearch MCP server exposes an optional argument inside its tool scheme allowing you to target a specific engine or chain multiple engines together.

When talking to **Claude Code CLI**, you can type your prompts explicitly to force a fallback:

-   **Target a different engine directly:**

    ```text
    "Use open-websearch with the duckduckgo engine to search for the current USD to ILS exchange rate."
    ```

-   **Force a fallback chain array:**

    ```text
    "Search for USD to ILS using open-websearch. Use brave, duckduckgo as engines."
    ```

Claude will look at the tool definitions provided by the MCP server and pass the correct engine array parameter to the backend.

3\. Fix the Bing "301 Redirect" Bot-Block

If you still want to utilize Bing, the engine block happens because your current `SEARCH_MODE` environment variable is implicitly set to `auto` or `request`, which uses raw HTTP requests that are easily blocked by Microsoft's anti-bot protections.

To fix the block, force the container to route Bing through its built-in headless browser engine (**Playwright**):

```bash
docker run -d \
  --name open-websearch-mcp \
  --restart unless-stopped \
  -e SEARCH_MODE=playwright \
  -p 127.0.0.1:5050:3000 \
  ghcr.io/aas-ee/open-web-search:latest
```

Use code with caution.

Setting `SEARCH_MODE=playwright` forces the container to launch a hidden browser window to simulate human interaction, which bypasses the `301` redirect and enables the default Bing behavior to succeed.

Would you like to configure a **free proxy** via `USE_PROXY=true` to help mask your Docker IP, or would you like to see how to bundle multiple engines together inside a **Docker Compose** file?

Share

More