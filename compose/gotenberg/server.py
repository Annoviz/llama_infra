"""FastMCP server that wraps Gotenberg's complete document conversion API.

Exposes tools for converting documents, web pages, and PDFs via Gotenberg
(Chromium + LibreOffice headless). Covers all v8 modules:
  - LibreOffice converters (DOCX/XLSX/PPTX → PDF)
  - Chromium converters (URL/HTML/Markdown → PDF)
  - Chromium screenshots (URL/HTML/Markdown → PNG)
  - PDF engine operations (merge, split, rotate, watermark, encrypt, etc.)

Usage:
    python server.py                     # runs on :8000
    MCP_PORT=9000 python server.py       # custom port
"""

import os
import re
from pathlib import Path
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://gotenberg:3000")
TIMEOUT = float(os.environ.get("GOTENBERG_TIMEOUT", "120"))  # generous for large docs

app = FastMCP(
    "gotenberg-converter",
    dependencies=["mcp", "httpx"],
)


# ── Shared helpers ────────────────────────────────────────────────────────────


def _resolve_output_path(filename: str, output_dir: Optional[str]) -> Path:
    """Return the full path for a converted/saved file."""
    if output_dir:
        target = Path(output_dir)
    else:
        target = Path.cwd() / "output"
    target.mkdir(parents=True, exist_ok=True)
    return target / filename


def _post_form(
    endpoint: str,
    files: Optional[dict] = None,
    data: Optional[dict] = None,
) -> httpx.Response:
    """POST multipart/form-data to Gotenberg and raise on HTTP errors.

    Always uses multipart/form-data even when there are no file uploads,
    because Gotenberg rejects application/x-www-form-urlencoded with 415.
    When files is empty/None, adds a dummy entry to force multipart encoding.
    """
    import io
    
    if not files:
        # Gotenberg requires multipart/form-data; httpx uses form-urlencoded
        # when only data= is provided. Add a no-op file field to force multipart.
        files = {"_gotenberg_dummy": ("_", io.BytesIO(b""), "application/octet-stream")}
    
    resp = httpx.post(f"{GOTENBERG_URL}{endpoint}", files=files, data=data or {}, timeout=TIMEOUT)
    if resp.status_code != 200:
        resp.raise_for_status()
    return resp


def _post_html(endpoint: str, html_content: str, extra_data: Optional[dict] = None) -> httpx.Response:
    """POST HTML content to Gotenberg as a file upload.

    Gotenberg's /forms/chromium/convert/html expects the HTML content as a file
    (index.html or an 'html' field), not as a form data field.
    """
    import io
    
    files = {
        "html": ("index.html", io.BytesIO(html_content.encode()), "text/html"),
    }
    
    resp_data = extra_data or {}
    resp = httpx.post(f"{GOTENBERG_URL}{endpoint}", files=files, data=resp_data, timeout=TIMEOUT)
    if resp.status_code != 200:
        resp.raise_for_status()
    return resp


def _markdown_to_html(md_content: str, title: Optional[str]) -> str:
    """Convert markdown content to a styled HTML document for Chromium rendering.

    Gotenberg's /forms/chromium/convert/markdown requires an index.html file with
    actual content — sending an empty HTML results in blank PDFs. This function
    converts common markdown syntax (headers, tables, bold, code blocks, etc.) into
    properly styled HTML that Chromium can render as a PDF.
    """
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
        """Check if a line looks like a markdown table row (has | delimiters)."""
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

        # Code blocks (fenced with ```)
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

        # Table row detection (lines with | separators, skip separator lines like |-|-|)
        if _is_table_row(stripped):
            # Skip separator rows (e.g., "|---|---|" or "|-------|")
            if re.match(r"^\|?[\s\-:]+\|", stripped):
                continue
            if not in_table:
                in_table = True
            table_rows.append(stripped)
            continue
        else:
            flush_table()
            in_table = False

        # Horizontal rule (only if no table context and line is only dashes/asterisks)
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            flush_code()
            html_lines.append("<hr>")
            continue

        # Headers
        header_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if header_match:
            flush_code()
            level = len(header_match.group(1))
            text = _inline_format(html_module.escape(header_match.group(2)))
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        # Blockquote
        if stripped.startswith("> "):
            flush_code()
            quote_text = _inline_format(html_module.escape(stripped[2:]))
            html_lines.append(f"<blockquote>{quote_text}</blockquote>")
            continue

        # Empty line
        if not stripped:
            flush_code()
            continue

        # Unordered list item
        li_match = re.match(r"^[-*+]\s+(.+)$", stripped)
        if li_match and not _is_table_row(stripped):
            html_lines.append(f"<li>{_inline_format(li_match.group(1))}</li>")
            continue

        # Ordered list item
        ol_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ol_match:
            html_lines.append(f"<li>{_inline_format(ol_match.group(1))}</li>")
            continue

        # Regular paragraph (collect consecutive non-list lines)
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
    # Inline code (must be before bold/italic to avoid conflicts)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Bold+Italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"___([^_]+)___", r"<strong><em>\1</em></strong>", text)
    # Bold
    text = re.sub(r"\*([^*]+)\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"_([^_]+)_", r"<em>\1</em>", text)
    return text


def _post_markdown(endpoint: str, md_content: str, extra_data: Optional[dict] = None) -> httpx.Response:
    """Convert markdown to styled HTML and POST via the html endpoint.

    Gotenberg's /forms/chromium/convert/markdown requires both index.html AND .md files
    but their interaction is unclear (may render both separately). Instead, we convert
    markdown to fully styled HTML ourselves and use /forms/chromium/convert/html which
    only needs a single file — reliable and predictable.
    """
    title = extra_data.get("title") if extra_data else None
    html_content = _markdown_to_html(md_content, title)
    # Use the html conversion endpoint instead of markdown endpoint
    return _post_html("/forms/chromium/convert/html", html_content, extra_data)


def _post_screenshot_html(endpoint: str, html_content: str, extra_data: Optional[dict] = None) -> httpx.Response:
    """POST HTML content for screenshot to Gotenberg as a file upload."""
    import io
    
    files = {
        "html": ("index.html", io.BytesIO(html_content.encode()), "text/html"),
    }
    
    resp_data = extra_data or {}
    resp = httpx.post(f"{GOTENBERG_URL}{endpoint}", files=files, data=resp_data, timeout=TIMEOUT)
    if resp.status_code != 200:
        resp.raise_for_status()
    return resp


def _post_screenshot_markdown(endpoint: str, md_content: str, extra_data: Optional[dict] = None) -> httpx.Response:
    """Convert markdown to styled HTML and POST for screenshot.

    Same approach as _post_markdown — generates styled HTML from markdown and uses
    the html endpoint which only needs a single file.
    """
    title = extra_data.get("title") if extra_data else None
    html_content = _markdown_to_html(md_content, title)
    return _post_screenshot_html("/forms/chromium/screenshot/html", html_content, extra_data)


def _error(msg: str) -> dict:
    return {"status": "error", "message": msg}


# ── LibreOffice: Document → PDF ───────────────────────────────────────────────


@app.tool()
def convert_docx_to_pdf(doc_path: str, output_dir: Optional[str] = None) -> dict:
    """Convert a DOCX/ODT Word document to PDF (LibreOffice Writer).

    Args:
        doc_path: Absolute path to .docx or .odt file.
                  Inside Docker this must be accessible via the container's filesystem,
                  or use convert_url_to_pdf() for remote URLs.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.

    Returns:
        dict with status, pdf_path, size_bytes, gotenberg_url (or error details).
    """
    full = Path(doc_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    output_path = _resolve_output_path(full.with_suffix(".pdf").name, output_dir)
    try:
        with open(full, "rb") as f:
            resp = _post_form("/forms/libreoffice/convert/to-pdf", files={"files": (full.name, f)})
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


@app.tool()
def convert_xlsx_to_pdf(spreadsheet_path: str, output_dir: Optional[str] = None) -> dict:
    """Convert an XLSX/XLS/ODS spreadsheet to PDF (LibreOffice Calc).

    Args:
        spreadsheet_path: Absolute path to .xlsx, .xls, or .ods file.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    full = Path(spreadsheet_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    output_path = _resolve_output_path(full.with_suffix(".pdf").name, output_dir)
    try:
        with open(full, "rb") as f:
            resp = _post_form("/forms/libreoffice/convert/to-pdf", files={"files": (full.name, f)})
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


@app.tool()
def convert_pptx_to_pdf(presentation_path: str, output_dir: Optional[str] = None) -> dict:
    """Convert a PPTX/PPT/ODP presentation to PDF (LibreOffice Impress).

    Args:
        presentation_path: Absolute path to .pptx, .ppt, or .odp file.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    full = Path(presentation_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    output_path = _resolve_output_path(full.with_suffix(".pdf").name, output_dir)
    try:
        with open(full, "rb") as f:
            resp = _post_form("/forms/libreoffice/convert/to-pdf", files={"files": (full.name, f)})
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── Chromium: Web Page → PDF ──────────────────────────────────────────────────


@app.tool()
def convert_url_to_pdf(url: str, output_dir: Optional[str] = None) -> dict:
    """Convert a remote web page URL to PDF (Chromium).

    Args:
        url: HTTP(S) URL of the web page to convert.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    basename = url.rstrip("/").split("/")[-1] or "document.pdf"
    output_path = _resolve_output_path(f"{Path(basename).with_suffix('.pdf').name}", output_dir)
    try:
        resp = _post_form("/forms/chromium/convert/url", data={"url": url})
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


@app.tool()
def convert_html_to_pdf(
    html_content: str,
    base_url: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Convert raw HTML content to PDF (Chromium).

    Args:
        html_content: Raw HTML string.
        base_url: Optional base URL for resolving relative resources (CSS, images).
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    output_path = _resolve_output_path("document.pdf", output_dir)
    try:
        extra_data = {}
        if base_url:
            extra_data["base_url"] = base_url
        resp = _post_html("/forms/chromium/convert/html", html_content, extra_data)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


@app.tool()
def convert_markdown_to_pdf(
    md_content: str,
    title: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Convert Markdown content to PDF (Chromium).

    Args:
        md_content: Raw Markdown string.
        title: Optional page title for the generated PDF.
        output_dir: Optional directory for the resulting PDF. Defaults to ./output/.
    """
    output_path = _resolve_output_path("document.pdf", output_dir)
    try:
        extra_data = {}
        if title:
            extra_data["title"] = title
        resp = _post_markdown("/forms/chromium/convert/markdown", md_content, extra_data)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── Chromium: Screenshot → PNG ────────────────────────────────────────────────


@app.tool()
def screenshot_url(url: str, output_dir: Optional[str] = None) -> dict:
    """Capture a PNG screenshot of a web page URL (Chromium).

    Args:
        url: HTTP(S) URL to screenshot.
        output_dir: Optional directory for the resulting PNG. Defaults to ./output/.
    """
    basename = url.rstrip("/").split("/")[-1] or "screenshot"
    output_path = _resolve_output_path(f"{Path(basename).with_suffix('.png').name}", output_dir)
    try:
        resp = _post_form("/forms/chromium/screenshot/url", data={"url": url})
        output_path.write_bytes(resp.content)
        return {"status": "ok", "image_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


@app.tool()
def screenshot_html(
    html_content: str,
    base_url: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Capture a PNG screenshot of raw HTML content (Chromium).

    Args:
        html_content: Raw HTML string.
        base_url: Optional base URL for relative resources.
        output_dir: Optional directory for the resulting PNG. Defaults to ./output/.
    """
    output_path = _resolve_output_path("screenshot.png", output_dir)
    try:
        extra_data = {}
        if base_url:
            extra_data["base_url"] = base_url
        resp = _post_screenshot_html("/forms/chromium/screenshot/html", html_content, extra_data)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "image_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


@app.tool()
def screenshot_markdown(
    md_content: str,
    title: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Capture a PNG screenshot of Markdown content (Chromium).

    Args:
        md_content: Raw Markdown string.
        title: Optional page title.
        output_dir: Optional directory for the resulting PNG. Defaults to ./output/.
    """
    output_path = _resolve_output_path("screenshot.png", output_dir)
    try:
        extra_data = {}
        if title:
            extra_data["title"] = title
        resp = _post_screenshot_markdown("/forms/chromium/screenshot/markdown", md_content, extra_data)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "image_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Merge ────────────────────────────────────────────────────────


@app.tool()
def pdf_merge(pdf_paths: list[str], output_dir: Optional[str] = None) -> dict:
    """Merge multiple PDF files into a single PDF.

    Args:
        pdf_paths: List of absolute paths to .pdf files (minimum 2).
        output_dir: Optional directory for the merged output. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    files_list = []
    for p in pdf_paths:
        full = Path(p)
        if not full.exists():
            return _error(f"File not found: {full}")
        files_list.append((full.name, open(full, "rb")))

    output_path = _resolve_output_path("merged.pdf", output_dir)
    try:
        resp = _post_form("/forms/pdfengines/merge", files={"files": files_list})
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Split ────────────────────────────────────────────────────────


@app.tool()
def pdf_split(
    pdf_path: str,
    pages: Optional[list[int]] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Split a PDF by page range or extract specific pages.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        pages: List of 1-indexed page numbers to extract. Omit for full split into individual files.
        output_dir: Optional directory for extracted pages. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path (first page if multi-split), size_bytes, and all_pages list.
    """
    full = Path(pdf_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {}
            if pages:
                # Gotenberg expects comma-separated page ranges like "1-3,5,7"
                page_ranges = []
                for p in sorted(pages):
                    page_ranges.append(str(p))
                data["pages"] = ",".join(page_ranges)

            resp = _post_form("/forms/pdfengines/split", files=files, data=data)

        if pages:
            output_path = _resolve_output_path(full.with_suffix("_split.pdf").name, output_dir)
            output_path.write_bytes(resp.content)
            return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
        else:
            # Full split: Gotenberg returns a zip archive
            import zipfile

            zip_name = full.with_suffix(".zip").name
            output_zip = _resolve_output_path(zip_name, output_dir)
            output_zip.write_bytes(resp.content)

            # Extract pages to numbered files
            extracted_pages = []
            with zipfile.ZipFile(output_zip) as zf:
                for i, info in enumerate(zf.infolist()):
                    page_out = _resolve_output_path(f"page_{i + 1}.pdf", output_dir)
                    page_out.write_bytes(zf.read(info.filename))
                    extracted_pages.append(str(page_out))

            return {
                "status": "ok",
                "zip_path": str(output_zip),
                "size_bytes": len(resp.content),
                "all_pages": extracted_pages,
            }
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Rotate ───────────────────────────────────────────────────────


@app.tool()
def pdf_rotate(
    pdf_path: str,
    angles_map: Optional[dict] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Rotate specific pages of a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        angles_map: Dict mapping 1-indexed page numbers to rotation degrees (90, 180, or 270).
                    If omitted, all pages are rotated by the default angle from data.
        output_dir: Optional directory for the result. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    full = Path(pdf_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {}
            if angles_map:
                # Gotenberg expects comma-separated page-angle pairs like "1=90,3=180"
                pairs = ",".join(f"{page}={angle}" for page, angle in sorted(angles_map.items()))
                data["pages-rotate"] = pairs

            resp = _post_form("/forms/pdfengines/rotate", files=files, data=data)

        output_path = _resolve_output_path(full.with_suffix("_rotated.pdf").name, output_dir)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Watermark ────────────────────────────────────────────────────


@app.tool()
def pdf_watermark(
    pdf_path: str,
    watermark_pdf: str,
    output_dir: Optional[str] = None,
) -> dict:
    """Add a watermark overlay to each page of a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        watermark_pdf: Absolute path to the watermark PDF (single-page recommended).
        output_dir: Optional directory for the result. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    full = Path(pdf_path)
    wm = Path(watermark_pdf)
    if not full.exists():
        return _error(f"Source file not found: {full}")
    if not wm.exists():
        return _error(f"Watermark file not found: {wm}")

    try:
        with open(full, "rb") as f1, open(wm, "rb") as f2:
            files = {"files": (full.name, f1), "watermarks": (wm.name, f2)}
            resp = _post_form("/forms/pdfengines/watermark", files=files)

        output_path = _resolve_output_path(full.with_suffix("_watermarked.pdf").name, output_dir)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Stamp ────────────────────────────────────────────────────────


@app.tool()
def pdf_stamp(
    pdf_path: str,
    stamp_pdf: str,
    positions: Optional[dict] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Stamp a PDF with an image or PDF overlay at specific page positions.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        stamp_pdf: Absolute path to the stamp image/PDF file.
        positions: Dict mapping 1-indexed pages to position config (see Gotenberg docs).
        output_dir: Optional directory for the result. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    full = Path(pdf_path)
    stamp = Path(stamp_pdf)
    if not full.exists():
        return _error(f"Source file not found: {full}")
    if not stamp.exists():
        return _error(f"Stamp file not found: {stamp}")

    try:
        with open(full, "rb") as f1, open(stamp, "rb") as f2:
            files = {"files": (full.name, f1), "stamps": (stamp.name, f2)}
            data = {}
            if positions:
                data["positions"] = str(positions)

            resp = _post_form("/forms/pdfengines/stamp", files=files, data=data)

        output_path = _resolve_output_path(full.with_suffix("_stamped.pdf").name, output_dir)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Flatten ──────────────────────────────────────────────────────


@app.tool()
def pdf_flatten(pdf_path: str, output_dir: Optional[str] = None) -> dict:
    """Flatten form fields and annotations in a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file (with forms).
        output_dir: Optional directory for the result. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    full = Path(pdf_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            resp = _post_form("/forms/pdfengines/flatten", files=files)

        output_path = _resolve_output_path(full.with_suffix("_flattened.pdf").name, output_dir)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Encrypt ──────────────────────────────────────────────────────


@app.tool()
def pdf_encrypt(
    pdf_path: str,
    owner_pw: str,
    user_pw: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Encrypt a PDF with password-based permissions.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        owner_pw: Owner password (full access).
        user_pw: User password (viewing/restrictions). If omitted, anyone can open.
        output_dir: Optional directory for the result. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    full = Path(pdf_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {"owner-password": owner_pw}
            if user_pw:
                data["user-password"] = user_pw
            resp = _post_form("/forms/pdfengines/encrypt", files=files, data=data)

        output_path = _resolve_output_path(full.with_suffix("_encrypted.pdf").name, output_dir)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Embed File ───────────────────────────────────────────────────


@app.tool()
def pdf_embed(
    pdf_path: str,
    file_to_attach: str,
    output_dir: Optional[str] = None,
) -> dict:
    """Embed an arbitrary file as an attachment inside a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        file_to_attach: Absolute path to the file to embed.
        output_dir: Optional directory for the result. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    full = Path(pdf_path)
    attach = Path(file_to_attach)
    if not full.exists():
        return _error(f"Source file not found: {full}")
    if not attach.exists():
        return _error(f"File to embed not found: {attach}")

    try:
        with open(full, "rb") as f1, open(attach, "rb") as f2:
            files = {"files": (full.name, f1), "attachments": (attach.name, f2)}
            resp = _post_form("/forms/pdfengines/embed", files=files)

        output_path = _resolve_output_path(full.with_suffix("_embedded.pdf").name, output_dir)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Metadata Read/Write ──────────────────────────────────────────


@app.tool()
def pdf_read_metadata(pdf_path: str) -> dict:
    """Read metadata (title, author, subject, etc.) from a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.

    Returns:
        Dict with status and metadata keys extracted by Chromium/PDF engines.
    """
    full = Path(pdf_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            resp = _post_form("/forms/pdfengines/metadata/read", files=files)

        # Gotenberg returns JSON metadata on success
        import json

        return {"status": "ok", "metadata": resp.json()}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


@app.tool()
def pdf_write_metadata(
    pdf_path: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    subject: Optional[str] = None,
    keywords: Optional[list[str]] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Write/set metadata on a PDF (title, author, subject, keywords).

    Args:
        pdf_path: Absolute path to the source .pdf file.
        title: Document title.
        author: Author name.
        subject: Subject/description.
        keywords: List of keyword strings.
        output_dir: Optional directory for the result. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    full = Path(pdf_path)
    if not full.exists():
        return _error(f"File not found: {full}")

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

        output_path = _resolve_output_path(full.with_suffix("_meta.pdf").name, output_dir)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Bookmarks Write ──────────────────────────────────────────────


@app.tool()
def pdf_write_bookmarks(
    pdf_path: str,
    bookmarks_json: str,
    output_dir: Optional[str] = None,
) -> dict:
    """Add or replace TOC bookmarks in a PDF.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        bookmarks_json: JSON string of bookmark tree (see Gotenberg docs for format).
                        Example: '[{"Title": "Introduction", "Page": 1, "Level": 0}]'
        output_dir: Optional directory for the result. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    full = Path(pdf_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {"bookmarks": bookmarks_json}
            resp = _post_form("/forms/pdfengines/bookmarks/write", files=files, data=data)

        output_path = _resolve_output_path(full.with_suffix("_bookmarked.pdf").name, output_dir)
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── PDF Engine: Convert to PDF/A / PDF/UA ────────────────────────────────────


@app.tool()
def pdf_convert_pdfa(
    pdf_path: str,
    pdfa_type: str = "pdfa",  # "pdfa" (PDF/A) or "pdfua" (PDF/UA)
    output_dir: Optional[str] = None,
) -> dict:
    """Convert a PDF to PDF/A archival format or PDF/UA universal accessibility.

    Args:
        pdf_path: Absolute path to the source .pdf file.
        pdfa_type: "pdfa" for PDF/A-2b (archival), "pdfua" for PDF/UA (accessibility).
        output_dir: Optional directory for the result. Defaults to ./output/.

    Returns:
        Dict with status, pdf_path, size_bytes (or error details).
    """
    full = Path(pdf_path)
    if not full.exists():
        return _error(f"File not found: {full}")

    try:
        with open(full, "rb") as f:
            files = {"files": (full.name, f)}
            data = {"type": pdfa_type}
            resp = _post_form("/forms/pdfengines/convert", files=files, data=data)

        output_path = _resolve_output_path(
            full.with_suffix(f"_{pdfa_type}.pdf").name, output_dir
        )
        output_path.write_bytes(resp.content)
        return {"status": "ok", "pdf_path": str(output_path), "size_bytes": len(resp.content)}
    except httpx.ConnectError as e:
        return _error(f"Cannot reach Gotenberg at {GOTENBERG_URL}: {e}")
    except httpx.HTTPStatusError as e:
        return _error(f"Gotenberg error HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        return _error(str(e))


# ── Entry point ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # Override host to 0.0.0.0 so Docker port mapping works
    app.settings.host = "0.0.0.0"
    
    # Allow all hosts for DNS rebinding protection (safe when behind reverse proxy / Docker network)
    if app.settings.transport_security:
        app.settings.transport_security.enable_dns_rebinding_protection = False
    
    transport = os.environ.get("MCP_TRANSPORT", "sse")
    if transport not in ("stdio", "sse", "streamable-http"):
        transport = "sse"
    app.run(transport=transport)
