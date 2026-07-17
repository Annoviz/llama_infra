# Skill: Gotenberg Document Conversion Suite

Convert documents, web pages, and PDFs using Gotenberg (Chromium + LibreOffice headless) via the MCP server on `http://localhost:${GOTENBERG_MCP_PORT:-3015}`.

## Prerequisites

Start the stack before running any tool:
```bash
make up-gotenberg    # Start Gotenberg + MCP server
make down-gotenberg  # Stop stack when done
```

MCP server exposes tools at `http://localhost:${GOTENBERG_MCP_PORT:-3015}`.

## Conversion Tools

### Document → PDF (LibreOffice)

Convert office documents to PDF via LibreOffice headless:

| Tool | Input | Description |
|------|-------|-------------|
| `convert_docx_to_pdf(doc_path, output_dir?)` | `.docx`, `.odt` | Word document → PDF |
| `convert_xlsx_to_pdf(spreadsheet_path, output_dir?)` | `.xlsx`, `.ods` | Spreadsheet → PDF |
| `convert_pptx_to_pdf(presentation_path, output_dir?)` | `.pptx`, `.odp` | Presentation → PDF |

**Usage:**
```python
# Local file path (must be accessible to the container)
result = await client.call_tool("convert_docx_to_pdf", {
    "doc_path": "/absolute/path/to/file.docx",
    "output_dir": "./output"  # optional, defaults to ./output/
})

# Remote URL — use convert_url_to_pdf instead (see below)
```

### Web Page → PDF / Screenshot (Chromium)

Convert web pages or raw HTML/markdown via headless Chromium:

| Tool | Input | Description |
|------|-------|-------------|
| `convert_url_to_pdf(url, output_dir?)` | HTTP(S) URL | Remote page → PDF |
| `convert_html_to_pdf(html_content, base_url?, output_dir?)` | Raw HTML string | HTML snippet → PDF |
| `convert_markdown_to_pdf(md_content, title?, output_dir?)` | Raw Markdown string | Markdown → PDF |

**Usage:**
```python
# Remote URL to PDF
result = await client.call_tool("convert_url_to_pdf", {
    "url": "https://example.com/report"
})

# Raw markdown with optional page title
result = await client.call_tool("convert_markdown_to_pdf", {
    "md_content": "# Report\n\nSome content...",
    "title": "Quarterly Report Q3 2025"
})

# HTML with base URL for resolving relative resources (CSS, images)
result = await client.call_tool("convert_html_to_pdf", {
    "html_content": "<h1>Hello</h1>",
    "base_url": "https://example.com/assets/"
})
```

### Screenshot Tools (Chromium)

Capture visual snapshots instead of PDFs:

| Tool | Input | Description |
|------|-------|-------------|
| `screenshot_url(url, output_dir?)` | HTTP(S) URL | Web page → PNG screenshot |
| `screenshot_html(html_content, base_url?, output_dir?)` | Raw HTML string | HTML snippet → PNG |
| `screenshot_markdown(md_content, title?, output_dir?)` | Raw Markdown string | Markdown → PNG |

**Usage:**
```python
result = await client.call_tool("screenshot_url", {
    "url": "https://example.com/dashboard"
})
# Returns: {"status": "ok", "image_path": "./output/dashboard.png", ...}
```

### PDF Manipulation Tools (PDF Engines)

Operate on existing PDFs — merge, split, rotate, watermark, encrypt, etc.:

| Tool | Input | Description |
|------|-------|-------------|
| `pdf_merge(pdf_paths[], output_dir?)` | List of `.pdf` paths | Merge multiple PDFs into one |
| `pdf_split(pdf_path, pages?, output_dir?)` | Single `.pdf` path | Split by page range or full split |
| `pdf_rotate(pdf_path, angles_map{}, output_dir?)` | `.pdf` + per-page angles | Rotate specific pages |
| `pdf_watermark(pdf_path, watermark_pdf, output_dir?)` | PDF + watermark overlay | Add watermark stamp |
| `pdf_stamp(pdf_path, stamp_pdf, positions?, output_dir?)` | PDF + stamp image/PDF | Place stamps at positions |
| `pdf_flatten(pdf_path, output_dir?)` | `.pdf` with forms | Flatten form fields and annotations |
| `pdf_encrypt(pdf_path, owner_pw, user_pw, output_dir?)` | `.pdf` + passwords | Encrypt/restrict PDF |
| `pdf_embed(pdf_path, file_to_attach, output_dir?)` | `.pdf` + attachment file | Embed file in PDF |
| `pdf_write_metadata(pdf_path, meta_dict, output_dir?)` | `.pdf` + metadata | Set title, author, subject, etc. |
| `pdf_read_metadata(pdf_path)` | `.pdf` path | Read PDF metadata |
| `pdf_write_bookmarks(pdf_path, bookmarks_list, output_dir?)` | `.pdf` + bookmark tree | Add/replace TOC bookmarks |
| `pdf_convert_pdfa(pdf_path, pdfa_type?, output_dir?)` | `.pdf` | Convert to PDF/A or PDF/UA |

**Usage:**
```python
# Merge multiple PDFs
result = await client.call_tool("pdf_merge", {
    "pdf_paths": ["./output/report.pdf", "./output/appendix.pdf"],
    "output_dir": "./merged"
})

# Split a large report into individual pages
result = await client.call_tool("pdf_split", {
    "pdf_path": "./output/big-report.pdf",
    "pages": [1, 3, 5]  # optional: specific page numbers, omit for full split
})

# Encrypt with permissions
result = await client.call_tool("pdf_encrypt", {
    "pdf_path": "./output/secret.pdf",
    "owner_pw": "owner-secret",
    "user_pw": "viewer-password"
})

# Add watermark
result = await client.call_tool("pdf_watermark", {
    "pdf_path": "./output/report.pdf",
    "watermark_pdf": "./assets/watermark.pdf"
})
```

### Combined Conversions (Chromium + PDF Engines in One Request)

All Chromium conversion endpoints (`/forms/chromium/convert/*`) accept the same form parameters as PDF engines. This means you can convert AND manipulate in a single request:

| Parameter | Applies To | Description |
|-----------|------------|-------------|
| `paper_size` | Chromium, LibreOffice | A4, Letter, Legal, etc. |
| `margin_*` | Chromium, LibreOffice | top, bottom, left, right (mm) |
| `orientation` | Chromium, LibreOffice | portrait / landscape |
| `watermark_pdf` | Chromium, LibreOffice + PDF output | Overlay watermark on converted PDF |
| `metadata_*` | Chromium, LibrePDF + PDF output | title, author, subject, keywords |

**Example:** Convert HTML to PDF with metadata and landscape orientation in one call:
```python
result = await client.call_tool("convert_html_to_pdf", {
    "html_content": "<h1>Report</h1>",
    # Chromium + PDF engine params in same request
    "paper_size": "A4",
    "orientation": "landscape",
    "metadata_title": "Annual Report 2025"
})
```

## Response Format

All tools return a dict:
```python
{
    "status": "ok",           # or "error"
    "pdf_path": "./output/file.pdf",   # output file path (for conversions)
    "image_path": "./output/screenshot.png",  # for screenshots
    "size_bytes": 123456,     # output size in bytes
    "gotenberg_url": "...",   # API endpoint used
    "message": "..."          # error details if status=="error"
}
```

## Error Handling

Common errors and fixes:

| Symptom | Cause | Fix |
|---------|-------|-----|
| `File not found` | Path not accessible inside container | Use host path that maps to volume, or use URL-based tools |
| `Cannot reach Gotenberg` | MCP server down / stack not running | Run `make up-gotenberg` |
| HTTP 500 from Gotenberg | LibreOffice conversion failed (corrupt file) | Verify source file opens in native app |
| Timeout after 120s | Large document or slow conversion | Set `GOTENBERG_TIMEOUT=300` and restart stack |

## API Reference

### Gotenberg v8 Endpoints Used

| Module | Endpoint | Tool(s) |
|--------|----------|---------|
| **LibreOffice** | `/forms/libreoffice/convert/to-pdf` | docx/xlsx/pptx → PDF |
| **Chromium Convert** | `/forms/chromium/convert/url` | URL → PDF |
| **Chromium Convert** | `/forms/chromium/convert/html` | HTML → PDF |
| **Chromium Convert** | `/forms/chromium/convert/markdown` | Markdown → PDF |
| **Chromium Screenshot** | `/forms/chromium/screenshot/url` | URL → PNG |
| **Chromium Screenshot** | `/forms/chromium/screenshot/html` | HTML → PNG |
| **Chromium Screenshot** | `/forms/chromium/screenshot/markdown` | Markdown → PNG |
| **PDF Engines** | `/forms/pdfengines/merge` | pdf_merge |
| **PDF Engines** | `/forms/pdfengines/split` | pdf_split |
| **PDF Engines** | `/forms/pdfengines/rotate` | pdf_rotate |
| **PDF Engines** | `/forms/pdfengines/watermark` | pdf_watermark |
| **PDF Engines** | `/forms/pdfengines/stamp` | pdf_stamp |
| **PDF Engines** | `/forms/pdfengines/flatten` | pdf_flatten |
| **PDF Engines** | `/forms/pdfengines/encrypt` | pdf_encrypt |
| **PDF Engines** | `/forms/pdfengines/embed` | pdf_embed |
| **PDF Engines** | `/forms/pdfengines/metadata/read` | pdf_read_metadata |
| **PDF Engines** | `/forms/pdfengines/metadata/write` | pdf_write_metadata |
| **PDF Engines** | `/forms/pdfengines/bookmarks/write` | pdf_write_bookmarks |
| **PDF Engines** | `/forms/pdfengines/convert` | pdf_convert_pdfa |

### Full Form Parameters by Endpoint

**LibreOffice (`/forms/libreoffice/convert/to-pdf`):**
- `files` (multipart): One or more documents to convert
- Paper size, margins, orientation, grayscale, fit-to-page

**Chromium Convert/Screenshot:**
- `url`: Remote URL to convert/screenshot
- `html` / `markdown`: Raw content strings
- `base_url`: Base URL for relative resources
- Paper size, margins, orientation, device scale factor, JS disabled, wait delay

**PDF Engines (merge, split, rotate, watermark, stamp, flatten, encrypt):**
- Vary by engine — see Gotenberg docs per-engine params. Merged via form data.

## Make Targets Reference

```bash
make up-gotenberg        # Start stack
make down-gotenberg      # Stop stack
make restart-gotenberg   # Restart both containers
make logs-gotenberg      # Tail logs
make config-gotenberg    # Validate compose config
make pull-gotenberg      # Pull images
```

## Notes

- Stack is **standalone** — independent of main/vLLM/llama.cpp stacks.
- MCP server connects to Gotenberg via Docker internal DNS (`http://gotenberg:3000`).
- Files passed as paths must be accessible inside the container (Docker volume mount or host path).
- For local files, ensure the file's directory is mounted into the gotenberg-mcp container.
