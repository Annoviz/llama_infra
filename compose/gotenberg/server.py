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
    """POST multipart/form-data to Gotenberg and raise on HTTP errors."""
    resp = httpx.post(f"{GOTENBERG_URL}{endpoint}", files=files, data=data, timeout=TIMEOUT)
    if resp.status_code != 200:
        resp.raise_for_status()
    return resp


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
        data = {"html": html_content}
        if base_url:
            data["base_url"] = base_url
        resp = _post_form("/forms/chromium/convert/html", data=data)
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
        data = {"markdown": md_content}
        if title:
            data["title"] = title
        resp = _post_form("/forms/chromium/convert/markdown", data=data)
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
        data = {"html": html_content}
        if base_url:
            data["base_url"] = base_url
        resp = _post_form("/forms/chromium/screenshot/html", data=data)
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
        data = {"markdown": md_content}
        if title:
            data["title"] = title
        resp = _post_form("/forms/chromium/screenshot/markdown", data=data)
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
    transport = os.environ.get("MCP_TRANSPORT", "sse")
    if transport not in ("stdio", "sse", "streamable-http"):
        transport = "sse"
    app.run(transport=transport)
