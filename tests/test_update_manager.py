import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "update_manager.py"
spec = importlib.util.spec_from_file_location("update_manager", MODULE_PATH)
update_manager = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["update_manager"] = update_manager
spec.loader.exec_module(update_manager)


class UpdateManagerTests(unittest.TestCase):
    def test_parse_requirements_line(self):
        self.assertEqual(
            update_manager.parse_requirements_line("fastapi>=0.100.0"),
            ("fastapi", ">=", "0.100.0"),
        )
        self.assertEqual(
            update_manager.parse_requirements_line("openai==1.64.0"),
            ("openai", "==", "1.64.0"),
        )
        self.assertEqual(
            update_manager.parse_requirements_line("jupyter"),
            ("jupyter", "", ""),
        )
        self.assertEqual(
            update_manager.parse_requirements_line("starlette-context>=0.3.6,<0.4"),
            ("starlette-context", "complex", ">=0.3.6,<0.4"),
        )
        self.assertEqual(
            update_manager.parse_requirements_line("# comment"), (None, None, None)
        )

    def test_is_newer_numeric(self):
        self.assertTrue(update_manager.is_newer("0.19.0", "0.18.3"))
        self.assertFalse(update_manager.is_newer("0.18.3", "0.18.3"))
        self.assertTrue(update_manager.is_newer("full-cuda-b5350", "full-cuda-b5343"))

    def test_apply_replacements_does_not_touch_frozen_file(self):
        with tempfile.TemporaryDirectory() as td:
            frozen_path = Path(td) / "requirements.txt"
            frozen_path.write_text("openai==1.0.0\n", encoding="utf-8")

            original_frozen = update_manager.REQ_FROZEN
            update_manager.REQ_FROZEN = frozen_path
            try:
                reps = [
                    update_manager.Replacement(
                        source_file=frozen_path,
                        old="openai==1.0.0",
                        new="openai==2.0.0",
                    )
                ]
                with self.assertRaises(RuntimeError):
                    update_manager.apply_replacements(
                        preview_only=False, replacements=reps
                    )
            finally:
                update_manager.REQ_FROZEN = original_frozen


# --- Pytest tests for update_manager with mocked network calls ---


def test_discover_docker_updates_with_mocked_docker_hub(mocker):
    """Test discover_docker_updates with mocked Docker Hub API responses."""
    # Use a version newer than the current one in compose file (0.32.1)
    mock_tags = ["0.32.2", "0.33.0", "0.34.0"]

    # Mock all the network calls in discover_docker_updates
    mocker.patch.object(update_manager, "docker_hub_tags", return_value=mock_tags)
    mocker.patch.object(update_manager, "ghcr_tags", return_value=["v1.0.0", "v1.1.0"])
    mocker.patch.object(update_manager, "latest_pypi_version", return_value="2.0.0")

    items = update_manager.discover_docker_updates()
    ollama_items = [i for i in items if i.name == "ollama/ollama"]

    assert len(ollama_items) >= 1
    assert ollama_items[0].kind == "docker"
    assert ollama_items[0].applyable is True


def test_discover_requirements_updates_with_mocked_pypi(mock_fetch_json):
    """Test discover_requirements_updates with mocked PyPI API responses."""
    mock_fetch_json.return_value = {
        "info": {"version": "2.0.0"},
    }

    items = update_manager.discover_requirements_updates()
    jupyter_items = [i for i in items if i.name == "jupyter"]

    assert len(jupyter_items) >= 1
    assert jupyter_items[0].kind == "python"
    assert jupyter_items[0].latest == "2.0.0"


def test_is_newer_prism_version():
    """PrismML release versions compare by build number (bXXXXX-sha)."""
    assert update_manager.is_newer("b10800-abc1234", "b10709-9a9394a")
    assert not update_manager.is_newer("b10709-9a9394a", "b10709-9a9394a")
    assert not update_manager.is_newer("b10687-5d80cff", "b10709-9a9394a")


def test_github_prism_version_parses_tag(mock_fetch_json):
    """github_prism_version strips the 'prism-' prefix and extracts the date."""
    mock_fetch_json.return_value = {
        "tag_name": "prism-b10800-abc1234",
        "published_at": "2026-10-01T10:00:00Z",
    }
    version, date = update_manager.github_prism_version()
    assert version == "b10800-abc1234"
    assert date == "2026-10-01"


def test_github_prism_version_rejects_bad_tag(mock_fetch_json):
    mock_fetch_json.return_value = {"tag_name": "v1.0.0"}
    assert update_manager.github_prism_version() == (None, None)


def test_github_prism_version_handles_error(mocker):
    mocker.patch.object(update_manager, "fetch_json", side_effect=Exception("boom"))
    assert update_manager.github_prism_version() == (None, None)


def test_discover_prism_updates(mocker):
    """discover_docker_updates reports a PrismML fork update from VERSIONS.env."""
    mocker.patch.object(update_manager, "github_prism_version",
                        return_value=("b10800-abc1234", "2026-10-01"))
    # Silence all other network calls
    mocker.patch.object(update_manager, "docker_hub_tags", return_value=[])
    mocker.patch.object(update_manager, "ghcr_tags", return_value=[])
    mocker.patch.object(update_manager, "latest_pypi_version", return_value=None)

    items = update_manager.discover_docker_updates()
    prism_items = [i for i in items if i.name == "PrismML-Eng/llama.cpp (PrismLM)"]

    assert len(prism_items) == 1
    item = prism_items[0]
    assert item.kind == "docker"
    assert item.latest == "b10800-abc1234"
    assert item.applyable is True
    assert item.date == "2026-10-01"
    assert item.source_file == update_manager.DOCKERFILE_LLAMA_PRISM


def test_build_replacements_prism(mocker, tmp_path):
    """build_replacements updates the router compose arg and the prism Dockerfile ARG."""
    router_file = tmp_path / "15-llamacpp-router.yml"
    router_file.write_text(
        "services:\n"
        "  llamacpp-router:\n"
        "    build:\n"
        "      args:\n"
        "        PRISM_LM_VERSION: ${PRISM_LM_VERSION:-b10709-9a9394a}\n",
        encoding="utf-8",
    )
    dockerfile = tmp_path / "Dockerfile.llamacpp-server-prism-ml"
    dockerfile.write_text(
        "ARG BASE_IMAGE=ghcr.io/ggml-org/llama.cpp:full-cuda13\n"
        "FROM ${BASE_IMAGE}\n"
        "ARG PRISM_LM_VERSION=b10709-9a9394a\n",
        encoding="utf-8",
    )

    original_router = update_manager.DOCKER_COMPOSE_LLAMA_ROUTER
    original_dockerfile = update_manager.DOCKERFILE_LLAMA_PRISM
    update_manager.DOCKER_COMPOSE_LLAMA_ROUTER = router_file
    update_manager.DOCKERFILE_LLAMA_PRISM = dockerfile
    try:
        item = update_manager.UpdateItem(
            kind="docker", name="PrismML-Eng/llama.cpp (PrismLM)",
            source_file=dockerfile, current="b10709-9a9394a", latest="b10800-abc1234",
            applyable=True, reason="GitHub release (PrismML fork)",
        )
        reps = update_manager.build_replacements([item])
    finally:
        update_manager.DOCKER_COMPOSE_LLAMA_ROUTER = original_router
        update_manager.DOCKERFILE_LLAMA_PRISM = original_dockerfile

    assert len(reps) == 2
    by_file = {r.source_file: (r.old, r.new) for r in reps}
    assert by_file[router_file] == (
        "PRISM_LM_VERSION: ${PRISM_LM_VERSION:-b10709-9a9394a}",
        "PRISM_LM_VERSION: ${PRISM_LM_VERSION:-b10800-abc1234}",
    )
    assert by_file[dockerfile] == (
        "ARG PRISM_LM_VERSION=b10709-9a9394a",
        "ARG PRISM_LM_VERSION=b10800-abc1234",
    )


def test_version_key_with_various_formats():
    """Test version_key handles various version string formats."""
    assert update_manager.version_key("0.19.0") == (0, 19, 0)
    assert update_manager.version_key("1.2.3.4") == (1, 2, 3, 4)
    assert update_manager.version_key("v1.0") == (1, 0)
    assert update_manager.version_key("no-numbers") == (0,)


def test_latest_tag_with_pattern_matching():
    """Test latest_tag correctly filters and sorts by pattern."""
    tags = ["v1.0.0", "v1.1.0", "v2.0.0", "1.0.0"]
    result = update_manager.latest_tag(tags, r"^v\d+(\.\d+){1,3}$")
    assert result == "v2.0.0"


def test_latest_pypi_version_handles_error(mock_fetch_json):
    """Test latest_pypi_version handles missing version gracefully."""
    mock_fetch_json.return_value = {"info": {}}
    result = update_manager.latest_pypi_version("nonexistent-package")
    assert result is None


@pytest.fixture
def mock_fetch_json(mocker):
    """Mock the fetch_json function for network calls."""
    return mocker.patch.object(update_manager, "fetch_json")


if __name__ == "__main__":
    unittest.main()
