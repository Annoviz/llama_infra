"""
check_doc_links.py - Verify that all local markdown links in docs/ and README.md
resolve to actual files within the repository.

Usage:
    python3 tools/check_doc_links.py

Exit codes:
    0  All links resolve
    1  One or more broken links found
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Markdown files to scan
SCAN_PATHS = [
    REPO_ROOT / "README.md",
    *sorted((REPO_ROOT / "docs").rglob("*.md")),
]

# Regex: matches [text](target) where target does not start with http/https/mailto/#
LINK_RE = re.compile(r"\[(?:[^\]]*)\]\((?!https?://|mailto:|#)([^)]+)\)")

broken: list[tuple[Path, int, str]] = []

for md_file in SCAN_PATHS:
    if not md_file.exists():
        continue
    base = md_file.parent
    for lineno, line in enumerate(md_file.read_text(encoding="utf-8").splitlines(), 1):
        for match in LINK_RE.finditer(line):
            raw_target = match.group(1).split("#")[0].strip()
            if not raw_target:
                continue
            target = (base / raw_target).resolve()
            if not target.exists():
                broken.append((md_file, lineno, match.group(1)))

if broken:
    print(f"❌ {len(broken)} broken local link(s) found:\n")
    for path, lineno, link in broken:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}:{lineno}  →  {link}")
    sys.exit(1)

print(f"✅ All local links resolve ({len(SCAN_PATHS)} files scanned).")
