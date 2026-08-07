FROM python:3.11-slim

# Install dependencies and the mcp server via pip
RUN pip install --no-cache-dir duckduckgo-mcp-server

# Expose the port your server listens on
EXPOSE 3000

# Run the server using the correct entry point
CMD ["python", "-m", "duckduckgo_mcp_server"]
