"""FastMCP server that wraps Gotenberg's complete document conversion API.

Exposes tools for converting documents, web pages, and PDFs via Gotenberg
(Chromium + LibreOffice headless). Covers all v8 modules:
  - LibreOffice converters (DOCX/XLSX/PPTX -> PDF)
  - Chromium converters (URL/HTML/Markdown -> PDF)
  - Chromium screenshots (URL/HTML/Markdown -> PNG)
  - PDF engine operations (merge, split, rotate, watermark, encrypt, etc.)

All tools return MCP-standard content blocks:
  - PDF tools: [TextContent(metadata), EmbeddedResource(base64 file)]
  - Screenshot tools: [TextContent(metadata), ImageContent(inline PNG)]
  - Metadata tools: TextContent(JSON metadata)

A resource template gotenberg://output/{filename} lets clients fetch any
converted file on demand via resources/read.

Usage:
    python server.py                     # runs on :8000
    MCP_PORT=9000 python server.py       # custom port
"""

import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import (
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    TextContent,
)

GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://gotenberg:3000")
TIMEOUT = float(os.environ.get("GOTENBERG_TIMEOUT", "120"))

app = FastMCP(
    "gotenberg-converter",
    dependencies=["mcp", "httpx"],
)


# ── Shared helpers ────────────────────────────────────────────────────────────


def _output_filename(input_name: str, output_ext: str) -> str:
    """Strip original extension and append the target extension."""
    stem = Path(input_name).stem
    return f"{stem}{output_ext}"


def _resolve_output_path(filename: str, output_dir: Optional[str]) -> Path:
    """Return the full path for a converted/saved file."""
    if output_dir:
        target = Path(output_dir)
    else:
        target = Path.cwd() / "output"
    target.mkdir(parents=True, exist_ok=True)
    return target / filename


def _embedded_resource(path: str, file_bytes: bytes, mime_type: str) -> EmbeddedResource:
    """Build an EmbeddedResource with base64-encoded binary data."""
    return EmbeddedResource(
        type="resource",
        resource=BlobResourceContents(
            uri=f"gotenberg://output/{Path(path).name}",
            mimeType=mime_type,
            blob=base64.b64encode(file_bytes).decode(),
        ),
    )


def _pdf_response(path: str, file_bytes: bytes) -> list[TextContent | EmbeddedResource]:
    """Build a standard success response: metadata JSON + embedded PDF."""
    return [
        TextContent(
            type="text",
            text=json.dumps({
                "status": "ok",
                "pdf_path": path,
                "size_bytes": len(file_bytes),
                "mime_type": "application/pdf",
            }),
        ),
        _embedded_resource(path, file_bytes, "application/pdf"),
    ]


def _image_response(path: str, file_bytes: bytes) -> list[TextContent | ImageContent]:
    """Build a screenshot response: metadata JSON + inline PNG image."""
    b64 = base64.b64encode(file_bytes).decode()
    return [
        TextContent(
            type="text",
            text=json.dumps({
                "status": "ok",
                "image_path": path,
                "size_bytes": len(file_bytes),
            }),
        ),
        ImageContent(
            type="image",
            data=b64,
            mimeType="image/png",
        ),
    ]


def _zip_response(path: str, file_bytes: bytes, all_pages: list[str]) -> list[TextContent | EmbeddedResource]:
    """Build a split-zip response: metadata JSON + embedded zip."""
    return [
        TextContent(
            type="text",
            text=json.dumps({
                "status": "ok",
                "zip_path": path,
                "size_bytes": len(file_bytes),
                "mime_type": "application/zip",
                "all_pages": all_pages,
            }),
        ),
        _embedded_resource(path, file_bytes, "application/zip"),
    ]


def _error_text(msg: str) -> TextContent:
    """Build an error response as TextContent."""
    return TextContent(
        type="text",
        text=json.dumps({"status": "error", "message": msg}),
    )


def _post_form(
    endpoint: str,
    files: Optional[dict] = None,
    data: Optional[dict] = None,
) -> httpx.Response:
    """POST multipart/form-data to Gotenberg and raise on HTTP errors."""
    if not files:
        files = {"_gotenberg_dummy": ("_", io.BytesIO(b""), "application/octet-stream")}

    resp = httpx.post(f"{GOTENBERG_URL}{endpoint}", files=files, data=data or {}, timeout=TIMEOUT)
    if resp.status_code != 200:
        resp.raise_for_status()
    return resp


def _post_html(endpoint: str, html_content: str, extra_data: Optional[dict] = None) -> httpx.Response:
    """POST HTML content to Gotenberg as a file upload."""
    files = {
        "html": ("index.html", io.BytesIO(html_content.encode()), "text/html"),
    }

    resp_data = extra_data or {}
    resp = httpx.post(f"{GOTENBERG_URL}{endpoint}", files=files, data=resp_data, timeout=TIMEOUT)
    if resp.status_code != 200:
        resp.raise_for_status()
    return resp


def _markdown_to_html(md_content: str, title: Optional[str]) -> str:
    """Convert markdown content to a styled HTML document for Chromium rendering."""
    import html as html_module

    css = """\
<style>
@page { margin: 2cm; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       line-height: 1.6; color: #1a1a1a; max-width: none; }
h1 { font-size: 2em; border-bottom: 2px solid #eaecef; padding-bottom: 0.3em; margin-top: 0; }
h2 { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 1.5em; }
h3 { font-size: 1.25em; margin-top: 1.2em; color: #24292f; }
h4, h5, h6 { margin-top: 1em; color: #24292f; }
hr { border: none; border-top: 1px solid #eaecef; margin: 1.5em 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #dfe2e5; padding: 8px 12px; text-align: left; }
th { background-color: #f6f8fa; font-weight: 600; }
tr:nth-child(even) { background-color: #fafbfc; }
strong, b { font-weight: 600; color: #1a1a1a; }
em, i { font-style: italic; }
p { margin: 0.5em 0; }
code { background-color: #f6f8fa; padding: 2px 6px; border-radius: 3px;
       font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
       font-size: 0.9em; }
pre { background-color: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto;
      margin: 1em 0; line-height: 1.45; }
pre code { background: none; padding: 0; font-size: 0.85em; }
blockquote { border-left: 4px solid #dfe2e5; margin: 1em 0; padding: 0.5em 1em;
             color: #6a737d; background-color: #fafbfc; }
ul, ol { padding-left: 2em; }
li { margin: 0.25em 0; }
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
</style>"""

    title_tag = f"<title>{html_module.escape(title)}</title>" if title else ""

    lines = md_content.split("\n")
    html_lines = []
    in_code_block = False
    code_buf = []
    in_table = False
    table_rows = []

    def _is_table_row(line: str) -> bool:
        return "|" in line and line.count("|") >= 2

    def flush_table():
        if not table_rows:
            return
        rows_html = []
        for i, row_text in enumerate(table_rows):
            cells = [html_module.escape(c.strip()) for c in row_text.split("|")[1:-1]]
            tag = "th" if i == 0 else "td"
            cells_html = "".join(f"<{tag}>{_inline_format(c)}</{tag}>" for c in cells)
            rows_html.append(f"<tr>{cells_html}</tr>")
        html_lines.append("<table>\n" + "\n".join(rows_html) + "\n</table>")
        table_rows.clear()

    def flush_code():
        if code_buf:
            inner = "\n".join(code_buf)
            html_lines.append(f"<pre><code>{html_module.escape(inner)}</code></pre>")
            code_buf.clear()

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code_block:
                flush_code()
                in_code_block = False
            else:
                flush_table()
                in_code_block = True
                code_buf = []
            continue

        if in_code_block:
            code_buf.append(stripped)
            continue

        if _is_table_row(stripped):
            if re.match(r"^\|?[\s\-:]+\|", stripped):
                continue
            if not in_table:
                in_table = True
            table_rows.append(stripped)
            continue
        else:
            flush_table()
            in_table = False

        if re.match(r"^[-*_]{3,}\s*$", stripped):
            flush_code()
            html_lines.append("<hr>")
            continue

        header_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if header_match:
            flush_code()
            level = len(header_match.group(1))
            text = _inline_format(html_module.escape(header_match.group(2)))
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        if stripped.startswith("> "):
            flush_code()
            quote_text = _inline_format(html_module.escape(stripped[2:]))
            html_lines.append(f"<blockquote>{quote_text}</blockquote>")
            continue

        if not stripped:
            flush_code()
            continue

        li_match = re.match(r"^[-*+]\s+(.+)$", stripped)
        if li_match and not _is_table_row(stripped):
            html_lines.append(f"<li>{_inline_format(li_match.group(1))}</li>")
            continue

        ol_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ol_match:
            html_lines.append(f"<li>{_inline_format(ol_match.group(1))}</li>")
            continue

        flush_code()
        formatted = _inline_format(html_module.escape(stripped))
        html_lines.append(f"<p>{formatted}</p>")

    flush_table()
    flush_code()

    body_content = "\n".join(html_lines)
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
{title_tag}
{css}
</head>
<body>
{body_content}
</body></html>"""


def _inline_format(text: str) -> str:
    """Apply inline markdown formatting (bold, italic, code)."""
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"___([^_]+)___", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
    text = re.sub(r"_([^_]+)_", r"<em>\1</em>", text)
    return text


def _post_markdown(endpoint: str, md_content: str, extra_data: Optional[dict] = None) -> httpx.Response:
    """Convert markdown to styled HTML and POST via the html endpoint."""
    title = extra_data.get("title") if extra_data else None
    html_content = _markdown_to_html(md_content, title)
    return _post_html("/forms/chromium/convert/html", html_content, extra_data)


def _post_screenshot_html(endpoint: str, html_content: str, extra_data: Optional[dict] = None) -> httpx.Response:
    """POST HTML content for screenshot to Gotenberg as a file upload."""
    files = {
        "html": ("index.html", io.BytesIO(html_content.encode()), "text/html"),
    }

    resp_data = extra_data or {}
    resp = httpx.post(f"{GOTENBERG_URL}{endpoint}", files=files, data=resp_data, timeout=TIMEOUT)
    if resp.status_code != 200:
        resp.raise_for_status()
    return resp


def _post_screenshot_markdown(endpoint: str, md_content: str, extra_data: Optional[dict] = None) -> httpx.Response:
    """Convert markdown to styled HTML and POST for screenshot."""
    title = extra_data.get("title") if extra_data else None
    html_content = _markdown_to_html(md_content, title)
    return _post_screenshot_html("/forms/chromium/screenshot/html", html_content, extra_data)


# ── Resource: on-demand file access ───────────────────────────────────────────


@app.resource("gotenberg://output/{filename}")
def get_output_file(filename: str) -> bytes:
    """Retrieve a converted file from the output directory."""
    path = Path("/app/output") / filename
    if not path.exists():
        raise FileNotFoundError(f"Output file not found: {filename}")
    return path.read_bytes()


# ── LibreOffice: Document -> PDF ──────────────────────────────────────────────


@app.tool()
def convert_docx_to_pdf(doc_path: str, output_dir: Optional[str] = None) -> list[TextContent | EmbeddedResource]:
    """Convert a DOCX/ODT Word document to PDF (LibreOffice Writer).

    Args:
        doc_path: Absolute path to .docx or .odt file.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.

    Returns:
        MCP content blocks with metadata and embedded PDF file.
    """
    full = Path(doc_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    output_path = _resolve_output_path(_output_filename(full.name, ".pdf"), output_dir)
    try:
        with open(full, "rb") as f:
            resp = _post_form("/forms/libreoffice/convert/to-pdf", files={"files": (full.name, f)})
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


@app.tool()
def convert_xlsx_to_pdf(spreadsheet_path: str, output_dir: Optional[str] = None) -> list[TextContent | EmbeddedResource]:
    """Convert an XLSX/XLS/ODS spreadsheet to PDF (LibreOffice Calc).

    Args:
        spreadsheet_path: Absolute path to .xlsx, .xls, or .ods file.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    full = Path(spreadsheet_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    output_path = _resolve_output_path(_output_filename(full.name, ".pdf"), output_dir)
    try:
        with open(full, "rb") as f:
            resp = _post_form("/forms/libreoffice/convert/to-pdf", files={"files": (full.name, f)})
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


@app.tool()
def convert_pptx_to_pdf(presentation_path: str, output_dir: Optional[str] = None) -> list[TextContent | EmbeddedResource]:
    """Convert a PPTX/PPT/ODP presentation to PDF (LibreOffice Impress).

    Args:
        presentation_path: Absolute path to .pptx, .ppt, or .odp file.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    full = Path(presentation_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    output_path = _resolve_output_path(_output_filename(full.name, ".pdf"), output_dir)
    try:
        with open(full, "rb") as f:
            resp = _post_form("/forms/libreoffice/convert/to-pdf", files={"files": (full.name, f)})
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── Chromium: Web Page -> PDF ─────────────────────────────────────────────────


@app.tool()
def convert_url_to_pdf(url: str, output_dir: Optional[str] = None) -> list[TextContent | EmbeddedResource]:
    """Convert a remote web page URL to PDF (Chromium).

    Args:
        url: HTTP(S) URL of the web page to convert.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    basename = url.rstrip("/").split("/")[-1] or "document"
    filename = _output_filename(basename, ".pdf")
    output_path = _resolve_output_path(filename, output_dir)
    try:
        resp = _post_form("/forms/chromium/convert/url", data={"url": url})
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


@app.tool()
def convert_html_to_pdf(
    html_content: str,
    filename: Optional[str] = None,
    base_url: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Convert raw HTML content to PDF (Chromium).

    Args:
        html_content: Raw HTML string.
        filename: Desired output filename (without extension). Defaults to "document".
        base_url: Optional base URL for resolving relative resources (CSS, images).
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    output_path = _resolve_output_path(
        _output_filename(filename or "document", ".pdf"), output_dir
    )
    try:
        extra_data = {}
        if base_url:
            extra_data["base_url"] = base_url
        resp = _post_html("/forms/chromium/convert/html", html_content, extra_data)
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


@app.tool()
def convert_markdown_to_pdf(
    md_content: str,
    filename: Optional[str] = None,
    title: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Convert Markdown content to PDF (Chromium).

    Args:
        md_content: Raw Markdown string.
        filename: Desired output filename (without extension). Defaults to "document".
        title: Optional page title for the generated PDF.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    output_path = _resolve_output_path(
        _output_filename(filename or "document", ".pdf"), output_dir
    )
    try:
        extra_data = {}
        if title:
            extra_data["title"] = title
        resp = _post_markdown("/forms/chromium/convert/markdown", md_content, extra_data)
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── Chromium: Screenshot -> PNG ───────────────────────────────────────────────


@app.tool()
def screenshot_url(url: str, output_dir: Optional[str] = None) -> list[TextContent | ImageContent]:
    """Capture a PNG screenshot of a web page URL (Chromium).

    Args:
        url: HTTP(S) URL to screenshot.
        output_dir: Optional directory for the resulting PNG. Defaults to ./output/.
    """
    basename = url.rstrip("/").split("/")[-1] or "screenshot"
    filename = _output_filename(basename, ".png")
    output_path = _resolve_output_path(filename, output_dir)
    try:
        resp = _post_form("/forms/chromium/screenshot/url", data={"url": url})
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _image_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


@app.tool()
def screenshot_html(
    html_content: str,
    filename: Optional[str] = None,
    base_url: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> list[TextContent | ImageContent]:
    """Capture a PNG screenshot of raw HTML content (Chromium).

    Args:
        html_content: Raw HTML string.
        filename: Desired output filename (without extension). Defaults to "screenshot".
        base_url: Optional base URL for relative resources.
        output_dir: Optional directory for the resulting PNG. Defaults to ./output/.
    """
    output_path = _resolve_output_path(
        _output_filename(filename or "screenshot", ".png"), output_dir
    )
    try:
        extra_data = {}
        if base_url:
            extra_data["base_url"] = base_url
        resp = _post_screenshot_html("/forms/chromium/screenshot/html", html_content, extra_data)
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _image_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


@app.tool()
def screenshot_markdown(
    md_content: str,
    filename: Optional[str] = None,
    title: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> list[TextContent | ImageContent]:
    """Capture a PNG screenshot of Markdown content (Chromium).

    Args:
        md_content: Raw Markdown string.
        filename: Desired output filename (without extension). Defaults to "screenshot".
        title: Optional page title.
        output_dir: Optional directory for the resulting PNG. Defaults to ./output/.
    """
    output_path = _resolve_output_path(
        _output_filename(filename or "screenshot", ".png"), output_dir
    )
    try:
        extra_data = {}
        if title:
            extra_data["title"] = title
        resp = _post_screenshot_markdown("/forms/chromium/screenshot/markdown", md_content, extra_data)
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _image_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Merge ────────────────────────────────────────────────────────


@app.tool()
def pdf_merge(pdf_paths: list[str], output_dir: Optional[str] = None) -> list[TextContent | EmbeddedResource]:
    """Merge multiple PDF files into a single PDF.

    Args:
        pdf_paths: List of absolute paths to .pdf files (minimum 2).
        output_dir: Optional directory for the merged output. Defaults to ./output/.

    Returns:
        MCP content blocks with metadata and embedded merged PDF.
    """
    file_handles = []
    try:
        for p in pdf_paths:
            full = Path(p)
            if not full.exists():
                return [_error_text(f"File not found: {full}")]
            file_handles.append(open(full, "rb"))

        files_list = [(Path(p).name, fh) for p, fh in zip(pdf_paths, file_handles)]
        output_path = _resolve_output_path("merged.pdf", output_dir)

        resp = _post_form("/forms/pdfengines/merge", files={"files": files_list})
        file_bytes = resp.content
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]
    finally:
        for fh in file_handles:
            fh.close()


# ── PDF Engine: Split ────────────────────────────────────────────────────────


@app.tool()
def pdf_split(
    pdf_path: str,
    pages: Optional[list[int]] = None,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Split a PDF by page range or extract specific pages.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        pages: List of 1-indexed page numbers to extract. Omit for full split into individual files.
        output_dir: Optional directory for extracted pages. Defaults to ./output/.

    Returns:
        MCP content blocks with metadata and embedded result (PDF or zip).
    """
    full = Path(pdf_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {}
            if pages:
                page_ranges = [str(p) for p in sorted(pages)]
                data["pages"] = ",".join(page_ranges)

            resp = _post_form("/forms/pdfengines/split", files=files, data=data)

        if pages:
            output_path = _resolve_output_path(_output_filename(full.name, "_split.pdf"), output_dir)
            file_bytes = resp.content
            output_path.write_bytes(file_bytes)
            return _pdf_response(str(output_path), file_bytes)
        else:
            import zipfile

            zip_name = _output_filename(full.name, ".zip")
            output_zip = _resolve_output_path(zip_name, output_dir)
            file_bytes = resp.content
            output_zip.write_bytes(file_bytes)

            extracted_pages = []
            with zipfile.ZipFile(output_zip) as zf:
                for i, info in enumerate(zf.infolist()):
                    page_out = _resolve_output_path(f"page_{i + 1}.pdf", output_dir)
                    page_out.write_bytes(zf.read(info.filename))
                    extracted_pages.append(str(page_out))

            return _zip_response(str(output_zip), file_bytes, extracted_pages)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Rotate ───────────────────────────────────────────────────────


@app.tool()
def pdf_rotate(
    pdf_path: str,
    angles_map: Optional[dict] = None,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Rotate specific pages of a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        angles_map: Dict mapping 1-indexed page numbers to rotation degrees (90, 180, or 270).
        output_dir: Optional directory for the result. Defaults to ./output/.
    """
    full = Path(pdf_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {}
            if angles_map:
                pairs = ",".join(f"{page}={angle}" for page, angle in sorted(angles_map.items()))
                data["pages-rotate"] = pairs

            resp = _post_form("/forms/pdfengines/rotate", files=files, data=data)

        file_bytes = resp.content
        output_path = _resolve_output_path(_output_filename(full.name, "_rotated.pdf"), output_dir)
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Watermark ────────────────────────────────────────────────────


@app.tool()
def pdf_watermark(
    pdf_path: str,
    watermark_pdf: str,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Add a watermark overlay to each page of a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        watermark_pdf: Absolute path to the watermark PDF (single-page recommended).
        output_dir: Optional directory for the result. Defaults to ./output/.
    """
    full = Path(pdf_path)
    wm = Path(watermark_pdf)
    if not full.exists():
        return [_error_text(f"Source file not found: {full}")]
    if not wm.exists():
        return [_error_text(f"Watermark file not found: {wm}")]

    try:
        with open(full, "rb") as f1, open(wm, "rb") as f2:
            files = {"files": (full.name, f1), "watermarks": (wm.name, f2)}
            resp = _post_form("/forms/pdfengines/watermark", files=files)

        file_bytes = resp.content
        output_path = _resolve_output_path(_output_filename(full.name, "_watermarked.pdf"), output_dir)
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Stamp ────────────────────────────────────────────────────────


@app.tool()
def pdf_stamp(
    pdf_path: str,
    stamp_pdf: str,
    positions: Optional[dict] = None,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Stamp a PDF with an image or PDF overlay at specific page positions.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        stamp_pdf: Absolute path to the stamp image/PDF file.
        positions: Dict mapping 1-indexed pages to position config.
        output_dir: Optional directory for the result. Defaults to ./output/.
    """
    full = Path(pdf_path)
    stamp = Path(stamp_pdf)
    if not full.exists():
        return [_error_text(f"Source file not found: {full}")]
    if not stamp.exists():
        return [_error_text(f"Stamp file not found: {stamp}")]

    try:
        with open(full, "rb") as f1, open(stamp, "rb") as f2:
            files = {"files": (full.name, f1), "stamps": (stamp.name, f2)}
            data = {}
            if positions:
                data["positions"] = str(positions)

            resp = _post_form("/forms/pdfengines/stamp", files=files, data=data)

        file_bytes = resp.content
        output_path = _resolve_output_path(_output_filename(full.name, "_stamped.pdf"), output_dir)
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Flatten ──────────────────────────────────────────────────────


@app.tool()
def pdf_flatten(pdf_path: str, output_dir: Optional[str] = None) -> list[TextContent | EmbeddedResource]:
    """Flatten form fields and annotations in a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file (with forms).
        output_dir: Optional directory for the result. Defaults to ./output/.
    """
    full = Path(pdf_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            resp = _post_form("/forms/pdfengines/flatten", files=files)

        file_bytes = resp.content
        output_path = _resolve_output_path(_output_filename(full.name, "_flattened.pdf"), output_dir)
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Encrypt ──────────────────────────────────────────────────────


@app.tool()
def pdf_encrypt(
    pdf_path: str,
    owner_pw: str,
    user_pw: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Encrypt a PDF with password-based permissions.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        owner_pw: Owner password (full access).
        user_pw: User password (viewing/restrictions). If omitted, anyone can open.
        output_dir: Optional directory for the result. Defaults to ./output/.
    """
    full = Path(pdf_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {"owner-password": owner_pw}
            if user_pw:
                data["user-password"] = user_pw
            resp = _post_form("/forms/pdfengines/encrypt", files=files, data=data)

        file_bytes = resp.content
        output_path = _resolve_output_path(_output_filename(full.name, "_encrypted.pdf"), output_dir)
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Embed File ───────────────────────────────────────────────────


@app.tool()
def pdf_embed(
    pdf_path: str,
    file_to_attach: str,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Embed an arbitrary file as an attachment inside a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        file_to_attach: Absolute path to the file to embed.
        output_dir: Optional directory for the result. Defaults to ./output/.
    """
    full = Path(pdf_path)
    attach = Path(file_to_attach)
    if not full.exists():
        return [_error_text(f"Source file not found: {full}")]
    if not attach.exists():
        return [_error_text(f"File to embed not found: {attach}")]

    try:
        with open(full, "rb") as f1, open(attach, "rb") as f2:
            files = {"files": (full.name, f1), "attachments": (attach.name, f2)}
            resp = _post_form("/forms/pdfengines/embed", files=files)

        file_bytes = resp.content
        output_path = _resolve_output_path(_output_filename(full.name, "_embedded.pdf"), output_dir)
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Metadata Read/Write ──────────────────────────────────────────


@app.tool()
def pdf_read_metadata(pdf_path: str) -> TextContent:
    """Read metadata (title, author, subject, etc.) from a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.

    Returns:
        TextContent with JSON metadata extracted by Gotenberg.
    """
    full = Path(pdf_path)
    if not full.exists():
        return _error_text(f"File not found: {full}")

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            resp = _post_form("/forms/pdfengines/metadata/read", files=files)

        return TextContent(
            type="text",
            text=json.dumps({"status": "ok", "metadata": resp.json()}),
        )
    except httpx.ConnectError as e:
        return _error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error_text(str(e))


@app.tool()
def pdf_write_metadata(
    pdf_path: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    subject: Optional[str] = None,
    keywords: Optional[list[str]] = None,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Write/set metadata on a PDF (title, author, subject, keywords).

    Args:
        pdf_path: Absolute path to the source .pdf file.
        title: Document title.
        author: Author name.
        subject: Subject/description.
        keywords: List of keyword strings.
        output_dir: Optional directory for the result. Defaults to ./output/.
    """
    full = Path(pdf_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {}
            if title:
                data["title"] = title
            if author:
                data["author"] = author
            if subject:
                data["subject"] = subject
            if keywords:
                data["keywords"] = ",".join(keywords)

            resp = _post_form("/forms/pdfengines/metadata/write", files=files, data=data)

        file_bytes = resp.content
        output_path = _resolve_output_path(_output_filename(full.name, "_meta.pdf"), output_dir)
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Bookmarks Write ──────────────────────────────────────────────


@app.tool()
def pdf_write_bookmarks(
    pdf_path: str,
    bookmarks_json: str,
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Add or replace TOC bookmarks in a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        bookmarks_json: JSON string of bookmark tree.
                        Example: '[{"Title": "Introduction", "Page": 1, "Level": 0}]'
        output_dir: Optional directory for the result. Defaults to ./output/.
    """
    full = Path(pdf_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {"bookmarks": bookmarks_json}
            resp = _post_form("/forms/pdfengines/bookmarks/write", files=files, data=data)

        file_bytes = resp.content
        output_path = _resolve_output_path(_output_filename(full.name, "_bookmarked.pdf"), output_dir)
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── PDF Engine: Convert to PDF/A / PDF/UA ────────────────────────────────────


@app.tool()
def pdf_convert_pdfa(
    pdf_path: str,
    pdfa_type: str = "pdfa",
    output_dir: Optional[str] = None,
) -> list[TextContent | EmbeddedResource]:
    """Convert a PDF to PDF/A archival format or PDF/UA universal accessibility.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        pdfa_type: "pdfa" for PDF/A-2b (archival), "pdfua" for PDF/UA (accessibility).
        output_dir: Optional directory for the result. Defaults to ./output/.
    """
    full = Path(pdf_path)
    if not full.exists():
        return [_error_text(f"File not found: {full}")]

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {"type": pdfa_type}
            resp = _post_form("/forms/pdfengines/convert", files=files, data=data)

        file_bytes = resp.content
        output_path = _resolve_output_path(
            _output_filename(full.name, f"_{pdfa_type}.pdf"), output_dir
        )
        output_path.write_bytes(file_bytes)
        return _pdf_response(str(output_path), file_bytes)
    except httpx.ConnectError as e:
        return [_error_text(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")]
    except httpx.HTTPStatusError as e:
        return [_error_text(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")]
    except Exception as e:
        return [_error_text(str(e))]


# ── Entry point ───────────────────────────────────────────────────────────────


def _build_combined_app():
    """Build a single Starlette ASGI app serving both SSE and streamable-http transports."""
    import contextlib

    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    from mcp.server.sse import SseServerTransport
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    sse_message_path = "/messages"

    sse_transport = SseServerTransport(
        sse_message_path,
        security_settings=app.settings.transport_security,
    )

    async def handle_sse(request: Request) -> Response:
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send  # type: ignore[attr-defined]
        ) as streams:
            await app._mcp_server.run(
                streams[0], streams[1], app._mcp_server.create_initialization_options()
            )
        return Response()

    session_manager = StreamableHTTPSessionManager(
        app=app._mcp_server,
        json_response=False,
        stateless=False,
        security_settings=app.settings.transport_security,
    )

    class _StreamableHttpApp:
        def __init__(self, mgr):
            self._mgr = mgr
        async def __call__(self, scope, receive, send):
            await self._mgr.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(starlette_app: Starlette):
        async with session_manager.run():
            yield

    return Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount(sse_message_path, app=sse_transport.handle_post_message),
            Route("/mcp", endpoint=_StreamableHttpApp(session_manager), methods=["GET", "POST", "DELETE"]),
        ],
        lifespan=lifespan,
    )


if __name__ == "__main__":
    app.settings.host = "0.0.0.0"

    if app.settings.transport_security:
        app.settings.transport_security.enable_dns_rebinding_protection = False

    import uvicorn

    port = int(os.environ.get("MCP_SERVER_PORT", "8000"))

    starlette_app = _build_combined_app()
    print(f"Serving both SSE (/sse) and streamable-http (/mcp) on port {port}")
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)
