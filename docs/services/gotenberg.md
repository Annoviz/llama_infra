# Gotenberg Service

Document conversion stack: Gotenberg (Chromium + LibreOffice headless) with a FastMCP server for programmatic doc-to-PDF conversion.

## Architecture

```
gotenberg-mcp (FastMCP, :3015)  → convert_docx_to_pdf(), convert_xlsx_to_pdf(), etc.
└── gotenberg (Gotenberg v8, :3010/internal:3000)
    └── Chromium + LibreOffice headless inside container
```

## Compose Files

| File | Purpose |
|------|---------|
| `compose/gotenberg/00-networks.yml` | Network (`gotenberg-network`) + volume (`gotenberg-data`) |
| `compose/gotenberg/10-gotenberg.yml` | Gotenberg container |
| `compose/gotenberg/20-gotenberg-mcp.yml` | FastMCP wrapper server |
| `compose/gotenberg/Dockerfile.gotenberg-mcp` | MCP server image (Python + mcp + httpx) |
| `compose/gotenberg/server.py` | MCP tools: convert_docx_to_pdf, convert_xlsx_to_pdf, etc. |

## Ports

- Host → Container: `${GOTENBERG_PORT:-3010}:3000` (Gotenberg API)
- Host → Container: `${GOTENBERG_MCP_PORT:-3015}:${MCP_SERVER_PORT:-8000}` (MCP streamable HTTP)

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOTENBERG_IMAGE` | `gotenberg/gotenberg:8` | Gotenberg Docker image tag |
| `GOTENBERG_PORT` | `3010` | Host port for Gotenberg API |
| `GOTENBERG_MCP_PORT` | `3015` | Host port for MCP server |
| `MCP_TRANSPORT` | `streamable-http` | MCP transport type (`sse`, `streamable-http`, or `stdio`) |
| `MCP_SERVER_PORT` | `8000` | Internal MCP container port |
| `MCP_API_KEY` | (empty) | Optional API key auth for MCP |
| `GOTENBERG_TIMEOUT` | `120` | HTTP timeout in seconds for conversions |

## Claude MCP Add

Add the Gotenberg MCP server to Claude Code:

```bash
claude mcp add gotenberg -- streamable-http http://localhost:3015/mcp
```

This registers all 20 tools (conversion, screenshot, PDF manipulation) as callable tools in Claude sessions.

## Output File Access

All conversion tools write output to `./output/<name>.pdf` **inside** the MCP container. The compose file mounts a host volume at `/app/output`, so files are accessible on the host at:

```
<project-root>/output/
```

For example, after calling `convert_docx_to_pdf`:
- Container path (returned in tool response): `/app/output/report.pdf`
- Host path (accessible from shell/Claude Code): `<repo>/output/report.pdf`

**Important:** The `output_dir` parameter is relative to the container's working directory (`/app`). Always use absolute paths like `/app/output/myfile.pdf` or omit it entirely to use the default. Relative paths (e.g., `./output`) will be resolved inside the container and still land in `<repo>/output/` thanks to the volume mount.

## Make Targets

```bash
make up-gotenberg       # Start Gotenberg + MCP server
make down-gotenberg     # Stop stack
make restart-gotenberg  # Restart both containers
make logs-gotenberg     # Tail Gotenberg container logs
make config-gotenberg   # Validate compose config
make pull-gotenberg     # Pull images
```

## MCP Tools (server.py)

| Tool | Input | Output Path Default |
|------|-------|---------------------|
| `convert_docx_to_pdf(doc_path, output_dir?)` | Local `.docx` or HTTP URL | `./output/<name>.pdf` |
| `convert_xlsx_to_pdf(spreadsheet_path, output_dir?)` | Local `.xlsx` | `./output/<name>.pdf` |
| `convert_pptx_to_pdf(presentation_path, output_dir?)` | Local `.pptx` | `./output/<name>.pdf` |
| `convert_markdown_to_pdf(md_content, title?, output_dir?)` | Raw Markdown string | `./output/document.pdf` |
| `convert_html_to_pdf(html_content, base_url?, output_dir?)` | Raw HTML string | `./output/document.pdf` |

Each tool returns: `{status, pdf_path, size_bytes, gotenberg_url}`.

## Notes

- **Standalone stack** — independent of main/vLLM/llama.cpp stacks. Start with `make up-gotenberg`.
- MCP server connects to Gotenberg via Docker internal DNS (`http://gotenberg:3000`).
- Gotenberg has a healthcheck; MCP depends on healthy gotenberg.
