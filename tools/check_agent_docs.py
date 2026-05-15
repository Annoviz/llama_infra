#!/usr/bin/env python3
"""Validate Markdown subagent docs under .github/agents.

This checker enforces a simple heading contract for subagent files so routing
instructions stay uniform and discoverable.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".github" / "agents"
ROUTER_FILE = ROOT / "AGENTS.md"

REQUIRED_HEADINGS = [
    "## Purpose",
    "## Owns",
    "## Triggers",
    "## Workflow",
    "## Boundaries",
    "## Handoff Back",
    "## Example Prompt",
]


def collect_agent_files(agents_dir: Path) -> List[Path]:
    """Return all markdown files in the subagent directory, including README."""
    files = sorted(p for p in agents_dir.glob("*.md"))
    return files


def required_headings() -> List[str]:
    return list(REQUIRED_HEADINGS)


def validate_agent_markdown(text: str) -> List[str]:
    errors: List[str] = []
    lines = text.splitlines()
    stripped = [line.strip() for line in lines]

    first_non_empty = next((line for line in stripped if line), "")
    if not first_non_empty.startswith("# "):
        errors.append("Missing top-level '# <Agent Name>' heading")

    for heading in REQUIRED_HEADINGS:
        if heading not in stripped:
            errors.append(f"Missing required heading: {heading}")

    return errors


def validate_file(path: Path) -> List[str]:
    return validate_agent_markdown(path.read_text(encoding="utf-8"))


def extract_agent_paths_from_router(text: str) -> List[str]:
    """Extract concrete .github/agents markdown paths from AGENTS.md text."""
    matches = re.findall(r"\.github/agents/[a-z0-9-]+\.md", text)
    return sorted(set(matches))


def validate_router_agent_paths(router_path: Path) -> List[str]:
    if not router_path.exists():
        return [f"Missing router file: {router_path.relative_to(ROOT)}"]

    text = router_path.read_text(encoding="utf-8")
    all_paths = re.findall(r"\.github/agents/[a-z0-9-]+\.md", text)
    paths = sorted(set(all_paths))
    errors: List[str] = []

    if not all_paths:
        errors.append("No concrete .github/agents/*.md paths found in AGENTS.md")
        return errors

    duplicates = sorted({path for path in all_paths if all_paths.count(path) > 1})
    for rel_path in duplicates:
        errors.append(f"Duplicate subagent path reference in AGENTS.md: {rel_path}")

    for rel_path in paths:
        if not (ROOT / rel_path).exists():
            errors.append(f"Referenced subagent path does not exist: {rel_path}")

    return errors


def run(paths: Iterable[Path]) -> int:
    failed = False
    for path in paths:
        errors = validate_file(path)
        if errors:
            failed = True
            print(f"{path.relative_to(ROOT)}")
            for item in errors:
                print(f"  - {item}")

    router_errors = validate_router_agent_paths(ROUTER_FILE)
    if router_errors:
        failed = True
        print(f"{ROUTER_FILE.relative_to(ROOT)}")
        for item in router_errors:
            print(f"  - {item}")

    if failed:
        print("\nAgent docs check failed.")
        return 1

    print("Agent docs check passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate .github/agents markdown docs")
    parser.add_argument(
        "--agents-dir",
        default=str(AGENTS_DIR),
        help="Path to subagent markdown directory",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    agents_dir = Path(args.agents_dir)
    files = collect_agent_files(agents_dir)
    if not files:
        print(f"No subagent markdown files found in {agents_dir}")
        return 1
    return run(files)


if __name__ == "__main__":
    raise SystemExit(main())

