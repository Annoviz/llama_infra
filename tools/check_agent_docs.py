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

# Agent names that should be defined in AGENTS.md
ROUTER_AGENT_NAMES = {
    "docker-ops-agent",
    "model-config-agent",
    "update-manager-agent",
    "docs-sync-agent",
    "coding-agent",
    "reviewer-agent",
    "commit-agent",
}


def collect_agent_files(agents_dir: Path) -> List[Path]:
    """Return all markdown files in the subagent directory, excluding archive."""
    archive_dir = agents_dir / "archive"
    files = sorted(p for p in agents_dir.glob("*.md") if not p.is_relative_to(archive_dir))
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
    """Validate AGENTS.md has all required agent sections and no duplicate references."""
    if not router_path.exists():
        return [f"Missing router file: {router_path.relative_to(ROOT)}"]

    text = router_path.read_text(encoding="utf-8")
    errors: List[str] = []

    # Extract agent names from AGENTS.md (### agent-name format)
    router_agent_names = set()
    for match in re.finditer(r"^### ([a-z0-9-]+)", text, re.MULTILINE):
        router_agent_names.add(match.group(1))

    # Check that all required agents are defined
    missing_agents = ROUTER_AGENT_NAMES - router_agent_names
    for agent_name in missing_agents:
        errors.append(f"Missing agent definition in AGENTS.md: {agent_name}")

    # Check for duplicate agent definitions
    agent_counts = {}
    for match in re.finditer(r"^### ([a-z0-9-]+)", text, re.MULTILINE):
        agent = match.group(1)
        agent_counts[agent] = agent_counts.get(agent, 0) + 1
    duplicates = [name for name, count in agent_counts.items() if count > 1]
    for agent_name in duplicates:
        errors.append(f"Duplicate agent definition in AGENTS.md: {agent_name}")

    # Check for archived files that aren't referenced (they should be in AGENTS.md)
    archive_dir = AGENTS_DIR / "archive"
    if archive_dir.exists():
        for archived_file in archive_dir.glob("*.md"):
            agent_name = archived_file.stem
            if agent_name not in ROUTER_AGENT_NAMES and agent_name != "routing-smoke":
                errors.append(f"Archived file '{archived_file.name}' not referenced in AGENTS.md")

    return errors


def validate_archived_agents(agents_dir: Path) -> List[str]:
    """Check archived agent files for consistency with AGENTS.md."""
    archive_dir = agents_dir / "archive"
    if not archive_dir.exists():
        return []

    errors: List[str] = []
    archived_files = sorted(archive_dir.glob("*.md"))

    # Extract agent names from AGENTS.md
    router_text = ROUTER_FILE.read_text(encoding="utf-8")
    router_agent_names = set()
    for match in re.finditer(r"^### ([a-z0-9-]+)", router_text, re.MULTILINE):
        router_agent_names.add(match.group(1))

    # Check archived files
    for archived_file in archived_files:
        agent_name = archived_file.stem
        if agent_name not in ROUTER_AGENT_NAMES and agent_name != "routing-smoke":
            errors.append(f"Archived file '{archived_file.name}' not referenced in AGENTS.md")

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

    archived_errors = validate_archived_agents(AGENTS_DIR)
    if archived_errors:
        failed = True
        print(f"{AGENTS_DIR.relative_to(ROOT)}/archive/")
        for item in archived_errors:
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

    # If no files in agents dir, check if AGENTS.md exists and has agent definitions
    if not files:
        if ROUTER_FILE.exists():
            router_text = ROUTER_FILE.read_text(encoding="utf-8")
            # Check if AGENTS.md contains agent definitions
            if re.search(r"^### [a-z0-9-]+", router_text, re.MULTILINE):
                print(f"Agent definitions found in {ROUTER_FILE.relative_to(ROOT)}")
                print("Note: Individual subagent files are archived in .github/agents/archive/")
                return run([])
        print(f"No subagent markdown files found in {agents_dir}")
        print("Note: Individual subagent files may be archived in .github/agents/archive/")
        return 1

    return run(files)


if __name__ == "__main__":
    raise SystemExit(main())
