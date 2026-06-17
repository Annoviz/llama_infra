"""Shared pytest fixtures for llama_infra tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def mock_agent_files(temp_dir: Path) -> Callable[[str, str], Path]:
    """Factory fixture to create agent markdown files."""

    def _create_agent(name: str, content: str = "") -> Path:
        agents_dir = temp_dir / ".github" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        path = agents_dir / f"{name}.md"
        if not content:
            content = f"""# {name}

## Purpose
Test agent for {name}

## Owns
Testing

## Triggers
Test triggers

## Workflow
Test workflow

## Boundaries
Test boundaries

## Handoff Back
Test handoff

## Example Prompt
Test example
"""
        path.write_text(content, encoding="utf-8")
        return path

    return _create_agent


@pytest.fixture
def sample_benchmark_results() -> list:
    """Sample benchmark results for testing."""
    from scripts.perf_test import BenchmarkResult

    return [
        BenchmarkResult(
            model="test-model",
            prompt_label="test prompt",
            first_token_ms=10.5,
            total_duration_s=2.0,
            input_tokens=10,
            output_tokens=50,
            tokens_per_sec=25.0,
        ),
        BenchmarkResult(
            model="test-model",
            prompt_label="test prompt",
            first_token_ms=12.3,
            total_duration_s=2.1,
            input_tokens=10,
            output_tokens=52,
            tokens_per_sec=24.76,
        ),
    ]
