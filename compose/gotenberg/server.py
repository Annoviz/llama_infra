"""FastMCP server that wraps Gotenberg's document conversion API.

Exposes tools for converting DOCX, XLSX, PPTX, Markdown and HTML to PDF via
Gotenberg (Chromium + LibreOffice headless).

Usage:
    python server.py                     # runs on :8000
    MCP_PORT=9000 python server.py       # custom port
"""

import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://gotenberg:3000")
TIMEOUT = float(os.environ.get("GOTENBERG_TIMEOUT", "120"))  # generous for large docs

app = FastMCP(
    "gotenberg-converter",
    dependencies=["mcp", "httpx"],
)


@app.tool()
def convert_docx_to_pdf(doc_path: str, output_dir: str | None = None) -> dict:
    """Convert a DOCX file to PDF using Gotenberg (LibreOffice headless).

    Args:
        doc_path: Absolute path to the .docx file.
                  When running inside Docker this must be accessible via the
                  container's filesystem, or use an http:// URL.
        output_dir: Optional directory to save the resulting PDF.
                    Defaults to ./output/<basename>.pdf relative to CWD.

    Returns:
        dict with keys: status, pdf_path, size_bytes, gotenberg_url
    """
    is_url = doc_path.startswith("http://") or doc_path.startswith("https://")

    if is_url:
        return _convert_via_url(doc_path, output_dir)
    else:
        return _upload_and_convert(doc_path, output_dir, form_type="writerdocument")


@app.tool()
def convert_xlsx_to_pdf(spreadsheet_path: str, output_dir: str | None = None) -> dict:
    """Convert an XLSX file to PDF using Gotenberg (LibreOffice headless).

    Args:
        spreadsheet_path: Absolute path to the .xlsx file.
        output_dir: Optional directory for the resulting PDF.

    Returns:
        dict with keys: status, pdf_path, size_bytes, gotenberg_url
    """
    return _upload_and_convert(spreadsheet_path, output_dir, form_type="spreadsheet")


@app.tool()
def convert_pptx_to_pdf(presentation_path: str, output_dir: str | None = None) -> dict:
    """Convert a PPTX file to PDF using Gotenberg (LibreOffice headless).

    Args:
        presentation_path: Absolute path to the .pptx file.
        output_dir: Optional directory for the resulting PDF.

    Returns:
        dict with keys: status, pdf_path, size_bytes, gotenberg_url
    """
    return _upload_and_convert(presentation_path, output_dir, form_type="presentation")


@app.tool()
def convert_markdown_to_pdf(
    md_content: str,
    title: str | None = None,
    output_dir: str | None = None,
) -> dict:
    """Convert Markdown content to PDF using Gotenberg (Chromium).

    Args:
        md_content: Raw Markdown string to convert.
        title: Optional page title for the generated PDF.
        output_dir: Optional directory for the resulting PDF.

    Returns:
        dict with keys: status, pdf_path, size_bytes, gotenberg_url
    """
    return _convert_markdown(md_content, title=title, output_dir=output_dir)


@app.tool()
def convert_html_to_pdf(
    html_content: str,
    base_url: str | None = None,
    output_dir: str | None = None,
) -> dict:
    """Convert HTML content to PDF using Gotenberg (Chromium).

    Args:
        html_content: Raw HTML string to convert.
        base_url: Optional base URL for resolving relative resources (CSS, images).
        output_dir: Optional directory for the resulting PDF.

    Returns:
        dict with keys: status, pdf_path, size_bytes, gotenberg_url
    """
    return _convert_html(html_content, base_url=base_url, output_dir=output_dir)


# ── Internal helpers ───────────────────────────────────────────────────────────


def _resolve_output_path(basename: str, output_dir: str | None) -> Path:
    """Return the full path for the converted PDF."""
    if output_dir:
        target = Path(output_dir)
    else:
        target = Path.cwd() / "output"
    target.mkdir(parents=True, exist_ok=True)
    return target / Path(basename).with_suffix(".pdf").name


def _upload_and_convert(
    file_path: str,
    output_dir: str | None,
    form_type: str,
) -> dict:
    """Upload a local document and convert via Gotenberg's LibreOffice API."""
    full_path = Path(file_path)

    if not full_path.exists():
        return {"status": "error", "message": f"File not found: {full_path}"}

    filename = full_path.name
    endpoint = f"/forms/libreoffice/{form_type}"
    api_url = f"{GOTENBERG_URL}{endpoint}"

    output_path = _resolve_output_path(filename, output_dir)

    try:
        with open(full_path, "rb") as f:
            files = {"files": (filename, f, "application/octet-stream")}
            resp = httpx.post(api_url, files=files, timeout=TIMEOUT)

        if resp.status_code != 200:
            return {
                "status": "error",
                "message": f"Gotenberg returned HTTP {resp.status_code}: {resp.text[:500]}",
                "gotenberg_url": api_url,
            }

        output_path.write_bytes(resp.content)

        return {
            "status": "ok",
            "pdf_path": str(output_path),
            "size_bytes": len(resp.content),
            "gotenberg_url": api_url,
        }
    except httpx.ConnectError as e:
        return {"status": "error", "message": f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _convert_via_url(url: str, output_dir: str | None) -> dict:
    """Convert a remote URL to PDF via Gotenberg's Chromium API."""
    endpoint = "/forms/chromium/convert/url"
    api_url = f"{GOTENBERG_URL}{endpoint}"

    basename = url.rstrip("/").split("/")[-1] or "document.pdf"
    output_path = _resolve_output_path(basename, output_dir)

    try:
        resp = httpx.post(api_url, data={"url": url}, timeout=TIMEOUT)

        if resp.status_code != 200:
            return {
                "status": "error",
                "message": f"Gotenberg returned HTTP {resp.status_code}: {resp.text[:500]}",
                "gotenberg_url": api_url,
            }

        output_path.write_bytes(resp.content)

        return {
            "status": "ok",
            "pdf_path": str(output_path),
            "size_bytes": len(resp.content),
            "gotenberg_url": api_url,
        }
    except httpx.ConnectError as e:
        return {"status": "error", "message": f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _convert_markdown(
    md_content: str,
    title: str | None,
    output_dir: str | None,
) -> dict:
    """Convert Markdown content to PDF via Gotenberg's Chromium API."""
    endpoint = "/forms/chromium/convert/markdown"
    api_url = f"{GOTENBERG_URL}{endpoint}"

    output_path = _resolve_output_path("document.pdf", output_dir)

    try:
        data: dict = {"markdown": md_content}
        if title:
            data["title"] = title

        resp = httpx.post(api_url, data=data, timeout=TIMEOUT)

        if resp.status_code != 200:
            return {
                "status": "error",
                "message": f"Gotenberg returned HTTP {resp.status_code}: {resp.text[:500]}",
                "gotenberg_url": api_url,
            }

        output_path.write_bytes(resp.content)

        return {
            "status": "ok",
            "pdf_path": str(output_path),
            "size_bytes": len(resp.content),
            "gotenberg_url": api_url,
        }
    except httpx.ConnectError as e:
        return {"status": "error", "message": f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _convert_html(
    html_content: str,
    base_url: str | None,
    output_dir: str | None,
) -> dict:
    """Convert HTML content to PDF via Gotenberg's Chromium API."""
    endpoint = "/forms/chromium/convert/html"
    api_url = f"{GOTENBERG_URL}{endpoint}"

    output_path = _resolve_output_path("document.pdf", output_dir)

    try:
        data: dict = {"html": html_content}
        if base_url:
            data["base_url"] = base_url

        resp = httpx.post(api_url, data=data, timeout=TIMEOUT)

        if resp.status_code != 200:
            return {
                "status": "error",
                "message": f"Gotenberg returned HTTP {resp.status_code}: {resp.text[:500]}",
                "gotenberg_url": api_url,
            }

        output_path.write_bytes(resp.content)

        return {
            "status": "ok",
            "pdf_path": str(output_path),
            "size_bytes": len(resp.content),
            "gotenberg_url": api_url,
        }
    except httpx.ConnectError as e:
        return {"status": "error", "message": f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    port = int(os.environ.get("MCP_SERVER_PORT", "8000"))
    app.run(transport="streamable-http", host="0.0.0.0", port=port)
