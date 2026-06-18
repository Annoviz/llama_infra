import importlib.util
import sys
import tempfile
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_agent_docs.py"
spec = importlib.util.spec_from_file_location("check_agent_docs", MODULE_PATH)
check_agent_docs = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["check_agent_docs"] = check_agent_docs
spec.loader.exec_module(check_agent_docs)


def test_validate_agent_markdown_passes_with_required_headings():
    content = """# sample-agent

## Purpose
## Owns
## Triggers
## Workflow
## Boundaries
## Handoff Back
## Example Prompt
"""
    assert check_agent_docs.validate_agent_markdown(content) == []


def test_validate_agent_markdown_reports_missing_heading():
    content = """# sample-agent

## Purpose
## Owns
## Triggers
## Workflow
## Boundaries
## Handoff Back
"""
    errors = check_agent_docs.validate_agent_markdown(content)
    assert any("## Example Prompt" in error for error in errors)


def test_validate_agent_markdown_reports_ordered_errors_for_malformed_doc():
    content = """sample-agent

## Purpose
"""
    errors = check_agent_docs.validate_agent_markdown(content)
    assert errors == [
        "Missing top-level '# <Agent Name>' heading",
        "Missing required heading: ## Owns",
        "Missing required heading: ## Triggers",
        "Missing required heading: ## Workflow",
        "Missing required heading: ## Boundaries",
        "Missing required heading: ## Handoff Back",
        "Missing required heading: ## Example Prompt",
    ]


def test_collect_agent_files_excludes_archive():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("# Index\n", encoding="utf-8")
        (root / "docker-ops-agent.md").write_text("# docker-ops-agent\n", encoding="utf-8")
        archive_dir = root / "archive"
        archive_dir.mkdir()
        (archive_dir / "old-agent.md").write_text("# old-agent\n", encoding="utf-8")

        files = check_agent_docs.collect_agent_files(root)
        assert [p.name for p in files] == ["README.md", "docker-ops-agent.md"]


def test_extract_agent_paths_from_router_finds_concrete_paths():
    router_text = """
    - `.github/agents/docker-ops-agent.md`
    - `.github/agents/reviewer-agent.md`
    - `.github/agents/*.md`
    """
    paths = check_agent_docs.extract_agent_paths_from_router(router_text)
    assert paths == [
        ".github/agents/docker-ops-agent.md",
        ".github/agents/reviewer-agent.md",
    ]


def test_validate_router_agent_paths_reports_missing_agents():
    """Test that missing agent definitions in AGENTS.md are reported."""
    with tempfile.TemporaryDirectory() as td:
        tmp_root = Path(td)
        router = tmp_root / "AGENTS.md"
        # Only include one agent, leaving others missing
        router.write_text(
            "# AGENTS.md\n\n### coding-agent\n## Purpose\nTest",
            encoding="utf-8",
        )
        agents_dir = tmp_root / ".github" / "agents"
        agents_dir.mkdir(parents=True)

        original_root = check_agent_docs.ROOT
        try:
            check_agent_docs.ROOT = tmp_root
            errors = check_agent_docs.validate_router_agent_paths(router)
        finally:
            check_agent_docs.ROOT = original_root

        # Should report missing agents (all except coding-agent)
        assert any("Missing agent definition in AGENTS.md: commit-agent" in e for e in errors)
        assert any("Missing agent definition in AGENTS.md: docker-ops-agent" in e for e in errors)


def test_validate_router_agent_paths_reports_duplicate_definition():
    """Test that duplicate agent definitions in AGENTS.md are reported."""
    with tempfile.TemporaryDirectory() as td:
        tmp_root = Path(td)
        router = tmp_root / "AGENTS.md"
        # Duplicate reviewer-agent definition
        router.write_text(
            "# AGENTS.md\n\n### reviewer-agent\n## Purpose\nTest\n\n### reviewer-agent\n## Purpose\nTest2",
            encoding="utf-8",
        )
        agents_dir = tmp_root / ".github" / "agents"
        agents_dir.mkdir(parents=True)

        original_root = check_agent_docs.ROOT
        try:
            check_agent_docs.ROOT = tmp_root
            errors = check_agent_docs.validate_router_agent_paths(router)
        finally:
            check_agent_docs.ROOT = original_root

        assert any("Duplicate agent definition in AGENTS.md: reviewer-agent" in e for e in errors)


def test_validate_router_agent_paths_passes_with_all_agents():
    """Test that AGENTS.md with all required agents passes validation."""
    with tempfile.TemporaryDirectory() as td:
        tmp_root = Path(td)
        router = tmp_root / "AGENTS.md"
        # Include all required agents
        agent_sections = ""
        for agent in check_agent_docs.ROUTER_AGENT_NAMES:
            agent_sections += f"\n### {agent}\n## Purpose\nTest\n"
        router.write_text("# AGENTS.md" + agent_sections, encoding="utf-8")
        agents_dir = tmp_root / ".github" / "agents"
        agents_dir.mkdir(parents=True)

        original_root = check_agent_docs.ROOT
        try:
            check_agent_docs.ROOT = tmp_root
            errors = check_agent_docs.validate_router_agent_paths(router)
        finally:
            check_agent_docs.ROOT = original_root

        assert errors == []


def test_archived_agents_validated():
    """Test that archived agents are validated against AGENTS.md."""
    with tempfile.TemporaryDirectory() as td:
        tmp_root = Path(td)
        router = tmp_root / "AGENTS.md"
        # Include all required agents
        agent_sections = ""
        for agent in check_agent_docs.ROUTER_AGENT_NAMES:
            agent_sections += f"\n### {agent}\n## Purpose\nTest\n"
        router.write_text("# AGENTS.md" + agent_sections, encoding="utf-8")
        agents_dir = tmp_root / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        archive_dir = agents_dir / "archive"
        archive_dir.mkdir()
        # Add an archived file that's not in AGENTS.md
        (archive_dir / "orphan-agent.md").write_text("# orphan-agent\n", encoding="utf-8")

        original_root = check_agent_docs.ROOT
        try:
            check_agent_docs.ROOT = tmp_root
            errors = check_agent_docs.validate_archived_agents(agents_dir)
        finally:
            check_agent_docs.ROOT = original_root

        assert any("orphan-agent" in e for e in errors)


def test_routing_smoke_content_in_agents_md():
    """Test that routing smoke cases are now in AGENTS.md."""
    agents_md = (
        Path(__file__).resolve().parents[1] / "AGENTS.md"
    ).read_text(encoding="utf-8")

    # Check for positive cases
    assert "| `commit-agent`" in agents_md
    assert "| `docker-ops-agent`" in agents_md
    assert "| `model-config-agent`" in agents_md

    # Check for negative cases section
    assert "Negative Cases" in agents_md or "Should Avoid" in agents_md

    # Check for clarification question example
    assert "Clarification question" in agents_md
