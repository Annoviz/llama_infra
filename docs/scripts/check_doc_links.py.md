# check_doc_links.py

## Purpose

Verify that all local markdown links in docs/ and README.md resolve to actual files within the repository.

## Usage

```bash
python3 tools/check_doc_links.py
make check-doc-links
```

## Description

Scans all markdown files in:
- `README.md`
- All files under `docs/`

Finds local markdown links (format: text in brackets followed by URL in parentheses) and verifies each target file exists. Links starting with http/https/mailto/# or # are excluded.

## Exit Codes

- `0` - All links resolve
- `1` - One or more broken links found

## See Also

- [../operations.md](../operations.md) - Code quality checks
