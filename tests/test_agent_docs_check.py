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


def test_collect_agent_files_includes_readme():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("# Index\n", encoding="utf-8")
        (root / "docker-ops-agent.md").write_text("# docker-ops-agent\n", encoding="utf-8")

        files = check_agent_docs.collect_agent_files(root)
        assert [p.name for p in files] == ["README.md", "docker-ops-agent.md"]


def test_agents_readme_passes_checker_contract():
    agents_readme = (
        Path(__file__).resolve().parents[1] / ".github" / "agents" / "README.md"
    )
    errors = check_agent_docs.validate_file(agents_readme)
    assert errors == []


