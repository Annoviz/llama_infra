#!/usr/bin/env python3
"""Validate Markdown subagent docs under .github/agents.

This checker enforces a simple heading contract for subagent files so routing
instructions stay uniform and discoverable.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".github" / "agents"

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


def run(paths: Iterable[Path]) -> int:
    failed = False
    for path in paths:
        errors = validate_file(path)
        if errors:
            failed = True
            print(f"{path.relative_to(ROOT)}")
            for item in errors:
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

