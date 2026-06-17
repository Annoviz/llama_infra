"""Tests for scripts/perf_test.py"""

import pytest

from scripts.perf_test import (
    BenchmarkResult,
    compute_aggregates,
    generate_run_id,
    prompt_label,
    run_benchmark,
    unique_prompt_label,
)


class TestGenerateRunId:
    """Tests for generate_run_id()."""

    def test_format(self):
        """Run ID should match format YYYYMMDD-HHMMSS-<6 chars>."""
        run_id = generate_run_id()
        # Split into date-time and suffix parts
        parts = run_id.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS
        assert len(parts[2]) == 6  # random suffix

    def test_uniqueness(self):
        """Multiple calls should produce different IDs."""
        ids = [generate_run_id() for _ in range(10)]
        assert len(set(ids)) == 10


class TestPromptLabel:
    """Tests for prompt_label()."""

    def test_short_prompt(self):
        """Short prompts should be returned unchanged."""
        prompt = "Hello world"
        assert prompt_label(prompt) == "Hello world"

    def test_truncation(self):
        """Long prompts should be truncated with ellipsis."""
        long_prompt = "This is a very long prompt that exceeds the limit"
        result = prompt_label(long_prompt, max_len=20)
        assert len(result) == 20
        assert result.endswith("…")

    def test_whitespace_collapsing(self):
        """Multiple whitespace should be collapsed to single space."""
        prompt = "hello    world   test"
        assert prompt_label(prompt) == "hello world test"

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert prompt_label("") == ""

    def test_custom_max_len(self):
        """Custom max_len should work."""
        prompt = "short"
        assert prompt_label(prompt, max_len=10) == "short"


class TestUniquePromptLabel:
    """Tests for unique_prompt_label()."""

    def test_no_collision(self):
        """Unique prompts should get their label unchanged."""
        seen = set()
        label1 = unique_prompt_label("Hello world", seen)
        assert label1 == "Hello world"
        assert "Hello world" in seen

    def test_collision_with_hash(self):
        """Colliding labels should get a hash suffix."""
        seen = set()
        # Create two prompts that truncate to the same label
        prompt1 = "This is a very long prompt that will be truncated"
        prompt2 = "This is a very long prompt that will be truncatd"

        label1 = unique_prompt_label(prompt1, seen)
        label2 = unique_prompt_label(prompt2, seen)

        # Labels should be different
        assert label1 != label2
        # Both should be in seen
        assert label1 in seen
        assert label2 in seen
        # Second one should have hash suffix
        assert "-" in label2

    def test_same_prompt_same_seen_set(self):
        """Same prompt with same seen set gets hash suffix on second call."""
        seen = set()
        label1 = unique_prompt_label("Hello world", seen)
        # Second call with same prompt detects collision and adds hash
        label2 = unique_prompt_label("Hello world", seen)
        assert label1 != label2  # Different due to hash suffix
        assert "Hello world" in label1
        assert "Hello world" in label2

    def test_same_prompt_different_seen_sets(self):
        """Same prompt with different seen sets gets same base label."""
        seen1 = set()
        seen2 = set()
        label1 = unique_prompt_label("Hello world", seen1)
        label2 = unique_prompt_label("Hello world", seen2)
        # Both should get the same base label since neither has seen it
        assert label1 == label2


class TestComputeAggregates:
    """Tests for compute_aggregates()."""

    def test_empty_list(self):
        """Empty list should return empty dict."""
        assert compute_aggregates([]) == {}

    def test_single_result(self):
        """Single result should return that result's values."""
        results = [
            BenchmarkResult(
                model="test",
                prompt_label="test",
                first_token_ms=10.0,
                total_duration_s=2.0,
                input_tokens=5,
                output_tokens=10,
                tokens_per_sec=5.0,
            )
        ]
        agg = compute_aggregates(results)
        assert agg["avg_first_token_ms"] == 10.0
        assert agg["min_first_token_ms"] == 10.0
        assert agg["max_first_token_ms"] == 10.0

    def test_multiple_results(self):
        """Multiple results should compute mean/min/max."""
        results = [
            BenchmarkResult(
                model="test",
                prompt_label="test",
                first_token_ms=10.0,
                total_duration_s=2.0,
                input_tokens=5,
                output_tokens=10,
                tokens_per_sec=5.0,
            ),
            BenchmarkResult(
                model="test",
                prompt_label="test",
                first_token_ms=20.0,
                total_duration_s=4.0,
                input_tokens=10,
                output_tokens=20,
                tokens_per_sec=5.0,
            ),
        ]
        agg = compute_aggregates(results)
        assert agg["avg_first_token_ms"] == 15.0
        assert agg["min_first_token_ms"] == 10.0
        assert agg["max_first_token_ms"] == 20.0

    def test_all_metrics_computed(self):
        """All expected metrics should be present."""
        results = [
            BenchmarkResult(
                model="test",
                prompt_label="test",
                first_token_ms=10.0,
                total_duration_s=2.0,
                input_tokens=5,
                output_tokens=10,
                tokens_per_sec=5.0,
            )
        ]
        agg = compute_aggregates(results)
        # Check that all expected metrics are present (iterations is also included)
        expected_keys = {
            "avg_first_token_ms",
            "min_first_token_ms",
            "max_first_token_ms",
            "avg_total_duration_s",
            "min_total_duration_s",
            "max_total_duration_s",
            "avg_input_tokens",
            "min_input_tokens",
            "max_input_tokens",
            "avg_output_tokens",
            "min_output_tokens",
            "max_output_tokens",
            "avg_tokens_per_sec",
            "min_tokens_per_sec",
            "max_tokens_per_sec",
            "iterations",
        }
        assert set(agg.keys()) == expected_keys


# --- Parametrized tests for edge cases ---


@pytest.mark.parametrize(
    "prompt,max_len,expected",
    [
        # Truncation at boundary
        ("a" * 28, 28, "a" * 28),
        ("a" * 29, 28, "a" * 27 + "…"),
        # Empty and whitespace
        ("", 28, ""),
        ("   ", 28, ""),
        # Single character
        ("x", 28, "x"),
        # Unicode characters (counted as single chars in Python)
        ("café", 28, "café"),
        # Long unicode string (31 chars total)
        ("a" * 30 + "é", 28, "a" * 27 + "…"),
    ],
)
def test_prompt_label_parametrized(prompt: str, max_len: int, expected: str):
    """Test prompt_label with various inputs."""
    assert prompt_label(prompt, max_len) == expected


@pytest.mark.parametrize(
    "results,expected_avg_first_token",
    [
        # All same values
        (
            [
                BenchmarkResult("m", "p", 10.0, 1.0, 5, 10, 10.0),
                BenchmarkResult("m", "p", 10.0, 1.0, 5, 10, 10.0),
            ],
            10.0,
        ),
        # Integer division edge case
        (
            [
                BenchmarkResult("m", "p", 10.0, 1.0, 5, 10, 10.0),
                BenchmarkResult("m", "p", 11.0, 1.0, 5, 10, 10.0),
            ],
            10.5,
        ),
        # Large values
        (
            [
                BenchmarkResult("m", "p", 1000.0, 100.0, 1000, 2000, 1000.0),
            ],
            1000.0,
        ),
        # Very small values
        (
            [
                BenchmarkResult("m", "p", 0.001, 0.001, 1, 1, 0.001),
            ],
            0.001,
        ),
    ],
)
def test_compute_aggregates_parametrized(results: list, expected_avg_first_token: float):
    """Test compute_aggregates with various result sets."""
    agg = compute_aggregates(results)
    assert agg["avg_first_token_ms"] == expected_avg_first_token


@pytest.mark.parametrize(
    "prompt,expected_collapsed",
    [
        ("hello    world", "hello world"),
        ("  leading and trailing  ", "leading and trailing"),
        ("multiple   spaces   here", "multiple spaces here"),
        ("\t tabs \n and newlines ", "tabs and newlines"),
    ],
)
def test_prompt_label_whitespace_collapsing(prompt: str, expected_collapsed: str):
    """Test that prompt_label collapses various whitespace types."""
    assert prompt_label(prompt) == expected_collapsed


@pytest.mark.parametrize(
    "seen_set,prompt,expected_differs",
    [
        # First occurrence gets base label
        (set(), "Hello world", True),
        # Second occurrence with same prompt gets hash suffix
        ({"Hello world"}, "Hello world", False),
        # Different prompt with same truncation gets different label
        ({"Hello world"}, "Hello world!", True),
    ],
)
def test_unique_prompt_label_parametrized(
    seen_set: set, prompt: str, expected_differs: bool
):
    """Test unique_prompt_label behavior with various seen sets."""
    label1 = unique_prompt_label(prompt, seen_set)
    label2 = unique_prompt_label(prompt, seen_set)

    if expected_differs:
        assert label1 != label2
    else:
        assert label1 == label2


# --- Integration tests with mock Ollama server ---


@pytest.mark.asyncio
async def test_run_benchmark_with_mock_ollama_server():
    """Test run_benchmark with a mock HTTP server simulating Ollama API."""
    import asyncio
    import json
    from aiohttp import web

    # Mock Ollama response (OpenAI-compatible)
    async def mock_chat_handler(request: web.Request) -> web.Response:
        body = await request.json()
        if body.get("stream"):
            # Stream response
            return web.Response(
                content_type="text/event-stream",
                text=(
                    'data: {"message": {"role": "assistant", "content": "test"}, "prompt_eval_count": 5, "eval_count": 10}\n\n'
                    "data: [DONE]\n\n"
                ),
            )
        return web.Response(status=400)  # Should not be called

    # Create mock server
    app = web.Application()
    app.router.add_post("/api/chat", mock_chat_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 0)  # Port 0 = auto-assign
    await site.start()

    try:
        port = site._server.sockets[0].getsockname()[1]
        base_url = f"http://localhost:{port}"

        config = {
            "base_url": base_url,
            "max_tokens": 128,
            "timeout": 10,
        }

        result = await asyncio.to_thread(
            run_benchmark, "test-model", "test prompt", config
        )

        assert result is not None
        assert result.model == "test-model"
        assert result.prompt_label == "test prompt"
        assert result.first_token_ms > 0
        assert result.total_duration_s > 0
        assert result.input_tokens == 5
        assert result.output_tokens == 10
        assert result.tokens_per_sec > 0

    finally:
        await runner.cleanup()


def test_run_benchmark_handles_network_error():
    """Test run_benchmark gracefully handles network errors."""
    config = {
        "base_url": "http://localhost:9999",  # Unreachable port
        "max_tokens": 128,
        "timeout": 1,
    }

    result = run_benchmark("test-model", "test prompt", config)
    assert result is None


def test_run_benchmark_handles_timeout(mocker):
    """Test run_benchmark handles timeout gracefully."""
    # Mock urllib.request.urlopen to raise TimeoutError
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = TimeoutError("Connection timed out")

    config = {
        "base_url": "http://localhost:11434",
        "max_tokens": 128,
        "timeout": 1,
    }

    result = run_benchmark("test-model", "test prompt", config)
    assert result is None


def test_run_benchmark_handles_empty_response(mocker):
    """Test run_benchmark handles empty response gracefully."""
    # Mock response that yields no data
    mock_response = mocker.MagicMock()
    mock_response.__iter__.return_value = iter([])

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    config = {
        "base_url": "http://localhost:11434",
        "max_tokens": 128,
        "timeout": 10,
    }

    result = run_benchmark("test-model", "test prompt", config)
    assert result is None
