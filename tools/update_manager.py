#!/usr/bin/env python3
"""Update manager for docker image tags and Python package versions.

Workflow:
- check: discover and print available updates
- suggest: same as check + write a proposal JSON file
- apply: discover updates, show diffs, ask interactive confirmation, and write changes

Safety:
- Updates only managed targets in compose/dockerfile/requirements-dev.txt
- Never edits workspace/requirements.txt
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROPOSAL = ROOT / ".update-manager-proposal.json"

DOCKER_COMPOSE_OLLAMA = ROOT / "compose/main/10-ollama.yml"
DOCKER_COMPOSE_ANYTHING = ROOT / "compose/main/20-anythingllm.yml"
DOCKER_COMPOSE_OPENWEBUI = ROOT / "compose/main/30-open-webui.yml"
DOCKER_COMPOSE_FALKORDB = ROOT / "compose/main/40-falkordb.yml"
DOCKER_COMPOSE_FALKORDB_MCP = ROOT / "compose/main/50-falkordb-mcp.yml"
DOCKER_COMPOSE_UNSLOTH = ROOT / "compose/main/60-unsloth.yml"
# llama.cpp stack — split compose files (replaced docker-compose.llama.cpp.yml)
DOCKER_COMPOSE_LLAMA_NATIVE = ROOT / "compose/llama/10-llamacpp-native.yml"
DOCKER_COMPOSE_LLAMA_ROUTER = ROOT / "compose/llama/15-llamacpp-router.yml"
DOCKER_COMPOSE_LLAMA_PY = ROOT / "compose/llama/20-llamacpp-py.yml"
DOCKER_COMPOSE_LLAMA_GATEWAY = ROOT / "compose/llama/25-llamacpp-router-gateway.yml"
DOCKERFILE_LLAMA_PY = ROOT / "compose/llama/Dockerfile.llamacpp-server-python"
DOCKER_COMPOSE_VLLM_ENGINE_BASE = ROOT / "compose/vllm/05-vllm-engine-base.yml"
DOCKER_COMPOSE_VLLM_GATEWAY = ROOT / "compose/vllm/40-vllm-gateway.yml"
DOCKERFILE_VLLM = ROOT / "compose/vllm/Dockerfile.vllm"

MAKEFILE = ROOT / "Makefile"
SERVICE_DOCS = [
    ROOT / "docs/services/ollama.md",
    ROOT / "docs/services/anythingllm.md",
    ROOT / "docs/services/open-webui.md",
    ROOT / "docs/services/falkordb.md",
    ROOT / "docs/services/falkordb-mcp.md",
    ROOT / "docs/services/unsloth.md",
    ROOT / "docs/services/llama-cpp.md",
]

REQ_DEV = ROOT / "requirements-dev.txt"
REQ_FROZEN = ROOT / "workspace/requirements.txt"
VERSIONS_ENV = ROOT / "VERSIONS.env"

# Map of version variable names to their compose files for discovery (reading current values)
VERSION_COMPOSE_MAP: Dict[str, Path] = {
    "OLLAMA_VERSION": DOCKER_COMPOSE_OLLAMA,
    "ANYTHINGLLM_VERSION": DOCKER_COMPOSE_ANYTHING,
    "OW_VERSION": DOCKER_COMPOSE_OPENWEBUI,
    "FALKORDB_VERSION": DOCKER_COMPOSE_FALKORDB,
    "FALKORDB_MCP_VERSION": DOCKER_COMPOSE_FALKORDB_MCP,
    "UNSLOTH_VERSION": DOCKER_COMPOSE_UNSLOTH,
    "MCP_GATEWAY_VERSION": ROOT / "compose/main/70-mcp-gateway.yml",
    "LLAMA_CPP_IMAGE": DOCKER_COMPOSE_LLAMA_NATIVE,
    "BASE_IMAGE": DOCKER_COMPOSE_LLAMA_PY,
    "LLAMA_CPP_VERSION": DOCKER_COMPOSE_LLAMA_PY,
    "VLLM_VERSION": DOCKERFILE_VLLM,
    "LITELLM_VERSION": DOCKER_COMPOSE_VLLM_GATEWAY,
    "HUGGINGFACE_HUB_VERSION": DOCKERFILE_VLLM,
}


@dataclass
class UpdateItem:
    kind: str
    name: str
    source_file: Path
    current: str
    latest: str
    applyable: bool
    reason: str
    date: Optional[str] = None


@dataclass
class Replacement:
    source_file: Path
    old: str
    new: str


def fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict:
    req = request.Request(url, headers=headers or {})
    with request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def version_key(value: str) -> Tuple[int, ...]:
    numbers = [int(x) for x in re.findall(r"\d+", value)]
    return tuple(numbers) if numbers else (0,)


def strip_date_from_tag(tag: str) -> Tuple[str, Optional[str]]:
    """Strip YYYY-MM-DD date suffix from a tag. Returns (base_tag, date_or_None)."""
    m = re.match(r"^(.+)-(\d{4}-\d{2}-\d{2})$", tag)
    if m:
        return m.group(1), m.group(2)
    return tag, None


def is_newer(latest: str, current: str) -> bool:
    # Strip date suffixes for comparison (e.g., full-cuda-b4738-2025-02-18 → full-cuda-b4738)
    latest_base, _ = strip_date_from_tag(latest)
    current_base, _ = strip_date_from_tag(current)

    # Floating CUDA tags (full-cuda13, full-cuda12) — always point to latest; never update
    # We prefer explicit build tags (full-cuda-bXXXX) or manually frozen versions (full-cuda13-9982)
    cuda_ver = re.compile(r"^(?:full|light|server)-cuda(\d+)$")
    if cuda_ver.match(current_base):
        return False
    # Legacy build-number tags (full-cuda-b5350) — compare build numbers
    full_cuda_build = re.compile(r"^full-cuda-b(\d+)$")
    latest_m = full_cuda_build.match(latest_base)
    current_m = full_cuda_build.match(current_base)
    if latest_m and current_m:
        return int(latest_m.group(1)) > int(current_m.group(1))
    return version_key(latest_base) > version_key(current_base)


def docker_hub_tags(repo: str, max_pages: int = 5) -> List[str]:
    tags: List[str] = []
    page = 1
    while page <= max_pages:
        url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags?page_size=100&page={page}"
        data = fetch_json(url)
        page_tags = [item.get("name", "") for item in data.get("results", [])]
        tags.extend([t for t in page_tags if t])
        if not data.get("next"):
            break
        page += 1
    return tags


def ghcr_token(namespace_repo: str) -> str:
    params = parse.urlencode({"scope": f"repository:{namespace_repo}:pull"})
    data = fetch_json(f"https://ghcr.io/token?{params}")
    token = data.get("token")
    if not token:
        raise RuntimeError(f"Unable to retrieve GHCR token for {namespace_repo}")
    return token


def get_ghcr_digest(namespace_repo: str, tag: str) -> Optional[str]:
    token = ghcr_token(namespace_repo)
    url = f"https://ghcr.io/v2/{namespace_repo}/manifests/{tag}"
    req = request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.docker.distribution.manifest.v2+json",
        },
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            return resp.headers.get("Docker-Content-Digest")
    except (error.HTTPError, error.URLError):
        return None


def get_image_date_by_inspect(repo_tag: str) -> Optional[str]:
    """Get creation date of an image from docker inspect. Returns YYYY-MM-DD or None."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "inspect", repo_tag, "--format={{.Created}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("T")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def get_tag_date(repo: str, tag: str) -> Optional[str]:
    """Get the creation date for a Docker image tag.

    Uses docker inspect (works for locally pulled/tagged images).
    Returns YYYY-MM-DD or None.
    """
    return get_image_date_by_inspect(f"{repo}:{tag}")


def append_date_to_tag(repo: str, tag: str) -> Optional[str]:
    """Append creation date to a Docker image tag if date is available."""
    date = get_tag_date(repo, tag)
    if date:
        return f"{tag}-{date}"
    return None


# --- VERSIONS.env helpers ---

_VERSIONS_HEADER = """\
# =============================================================================
# Docker Image & Python Package Version Defaults
# =============================================================================
# Managed by tools/update_manager.py — do not edit manually.
# Override per-environment in .env (loaded via -include in Makefile).
# Usage: docker-compose reads this automatically; Makefile loads it explicitly.
# =============================================================================

"""


def _read_versions_env() -> Dict[str, str]:
    """Read current values from VERSIONS.env as a dict."""
    if not VERSIONS_ENV.exists():
        return {}
    result: Dict[str, str] = {}
    for line in VERSIONS_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m:
            result[m.group(1)] = m.group(2).strip()
    return result


def _write_versions_env(updates: Dict[str, str]) -> None:
    """Write updated values to VERSIONS.env preserving header and comments."""
    existing = {}
    if VERSIONS_ENV.exists():
        for line in VERSIONS_ENV.read_text(encoding="utf-8").splitlines(keepends=True):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", stripped)
            if m:
                existing[m.group(1)] = m.group(2).strip()

    # Merge updates into existing values (updates take precedence)
    merged = {**existing, **updates}

    lines = [_VERSIONS_HEADER]

    sections = [
        ("--- Main Stack ---", ["OLLAMA_VERSION", "ANYTHINGLLM_VERSION", "OW_VERSION",
                                 "FALKORDB_VERSION", "FALKORDB_MCP_VERSION", "UNSLOTH_VERSION",
                                 "MCP_GATEWAY_VERSION"]),
        ("--- llama.cpp Stack ---", ["LLAMA_CPP_IMAGE", "BASE_IMAGE", "LLAMA_CPP_VERSION"]),
        ("--- vLLM Stack ---", ["VLLM_VERSION", "LITELLM_VERSION", "HUGGINGFACE_HUB_VERSION"]),
    ]

    for section_title, var_names in sections:
        lines.append(f"# {section_title}")
        found_any = False
        for name in var_names:
            if name in merged:
                lines.append(f"{name}={merged[name]}")
                found_any = True
        if found_any:
            lines.append("")

    # Add any extra vars not in predefined sections
    extra = {k: v for k, v in merged.items() if k not in (n for _, ns in sections for n in ns)}
    if extra:
        lines.append("# --- Other ---")
        for name, value in sorted(extra.items()):
            lines.append(f"{name}={value}")
        lines.append("")

    VERSIONS_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ghcr_tags(namespace_repo: str) -> List[str]:
    token = ghcr_token(namespace_repo)
    data = fetch_json(
        f"https://ghcr.io/v2/{namespace_repo}/tags/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    tags = data.get("tags", []) or []
    return tags


def latest_tag(tags: Iterable[str], pattern: str) -> Optional[str]:
    regex = re.compile(pattern)
    candidates = [t for t in tags if regex.match(t)]
    if not candidates:
        return None
    return sorted(candidates, key=version_key)[-1]


def latest_pypi_version(package_name: str) -> Optional[str]:
    data = fetch_json(f"https://pypi.org/pypi/{parse.quote(package_name)}/json")
    version = data.get("info", {}).get("version")
    return str(version) if version else None


def github_release_version(owner: str, repo: str) -> Optional[str]:
    """Get latest release tag from GitHub API (fallback for repos that don't publish versioned tags to GHCR)."""
    try:
        data = fetch_json(f"https://api.github.com/repos/{owner}/{repo}/releases/latest")
        return data.get("tag_name")
    except Exception:
        return None


def parse_requirements_line(
    line: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None, None, None

    m_eq = re.match(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)$", line)
    if m_eq:
        return m_eq.group(1), "==", m_eq.group(2)

    m_ge = re.match(r"^([A-Za-z0-9_.-]+)>=([A-Za-z0-9_.+-]+)$", line)
    if m_ge:
        return m_ge.group(1), ">=", m_ge.group(2)

    m_plain = re.match(r"^([A-Za-z0-9_.-]+)$", line)
    if m_plain:
        return m_plain.group(1), "", ""

    # Keep advanced constraints visible in reports but avoid auto-rewriting them.
    m_complex = re.match(r"^([A-Za-z0-9_.-]+)([<>=!~].+)$", line)
    if m_complex:
        return m_complex.group(1), "complex", m_complex.group(2)

    return None, None, None


def discover_docker_updates() -> List[UpdateItem]:
    """Discover Docker image updates by reading versions from VERSIONS.env."""
    items: List[UpdateItem] = []
    ver = _read_versions_env()

    # Helper to create UpdateItem from a version variable
    def make_item(var_name: str, pkg_name: str, source_file: Path,
                  pattern: Optional[str], reason: str) -> None:
        current_val = ver.get(var_name)
        if not current_val:
            return

        try:
            if pattern is None:
                latest = None
            elif "pypi" in reason.lower():
                latest = latest_pypi_version(pkg_name)
            elif pkg_name == "open-webui/open-webui":
                # GHCR namespace/repo is the full path for open-webui.
                # GHCR only has git-SHA tags; fall back to GitHub releases API for versioned tags.
                all_tags = ghcr_tags("open-webui/open-webui")
                latest = latest_tag(all_tags, pattern)
                if not latest:
                    latest = github_release_version("open-webui", "open-webui")
            else:
                latest = latest_tag(docker_hub_tags(pkg_name), pattern)
        except (error.HTTPError, error.URLError):
            latest = None

        if not latest:
            return

        items.append(
            UpdateItem(
                kind="docker", name=pkg_name, source_file=source_file,
                current=current_val, latest=latest,
                applyable=is_newer(latest, current_val), reason=reason,
            )
        )

    # Main Stack
    make_item("OLLAMA_VERSION", "ollama/ollama", DOCKER_COMPOSE_OLLAMA,
              r"^\d+(\.\d+){1,3}$", "Docker Hub tag")
    make_item("ANYTHINGLLM_VERSION", "mintplexlabs/anythingllm", DOCKER_COMPOSE_ANYTHING,
              r"^\d+(\.\d+){1,3}$", "Docker Hub tag")
    make_item("OW_VERSION", "open-webui/open-webui", DOCKER_COMPOSE_OPENWEBUI,
              r"^v?\d+(\.\d+){1,3}$", "GHCR tag")
    make_item("FALKORDB_VERSION", "falkordb/falkordb", DOCKER_COMPOSE_FALKORDB,
              r"^v?\d+(\.\d+){1,3}$", "Docker Hub tag")
    make_item("FALKORDB_MCP_VERSION", "falkordb/mcpserver", DOCKER_COMPOSE_FALKORDB_MCP,
              r"^\d+(\.\d+){1,3}$", "Docker Hub tag")
    make_item("UNSLOTH_VERSION", "unsloth/unsloth", DOCKER_COMPOSE_UNSLOTH,
              r"^[0-9]+\.[0-9]+\.[0-9]+.*$", "Docker Hub tag")
    make_item("MCP_GATEWAY_VERSION", "docker/mcp-gateway", ROOT / "compose/main/70-mcp-gateway.yml",
              None, "GHCR/Docker Hub (manual check)")

    # llama.cpp Stack — use fixed CUDA version tags as canonical references.
    # full-cuda13, full-cuda12 etc are our pinned "latest" for each CUDA version.
    # Build-number tags (full-cuda-bXXXX) are legacy; we compare dates to detect new builds.
    current_llama = ver.get("LLAMA_CPP_IMAGE") or ver.get("BASE_IMAGE")
    if current_llama:
        current_base, _ = strip_date_from_tag(current_llama)

        # Determine which CUDA version tag to use as canonical reference
        cuda_ver_match = re.match(r"^(?:full|light|server)-cuda(\d+)$", current_base)
        if cuda_ver_match:
            cuda_version = cuda_ver_match.group(1)
            fixed_tag = f"full-cuda{cuda_version}"  # e.g., full-cuda13, full-cuda12

            new_date = get_tag_date("ghcr.io/ggml-org/llama.cpp", fixed_tag) or "date-unavailable"
            current_date = get_tag_date("ghcr.io/ggml-org/llama.cpp", strip_date_from_tag(current_llama)[0])

            is_actually_newer = False
            if new_date != "date-unavailable" and current_date:
                # Compare dates — only update if new image was built after existing
                try:
                    is_actually_newer = new_date > current_date.replace("-", "") or new_date > current_date
                except (ValueError, AttributeError):
                    pass

            date_tagged_latest = f"{fixed_tag}-{new_date}" if new_date != "date-unavailable" else fixed_tag

            items.append(
                UpdateItem(
                    kind="docker", name=f"ghcr.io/ggml-org/llama.cpp:full-cuda{cuda_version}",
                    source_file=DOCKER_COMPOSE_LLAMA_NATIVE, current=current_llama,
                    latest=date_tagged_latest, applyable=is_actually_newer,
                    reason=f"CUDA {cuda_version} fixed tag (date comparison)",
                    date=new_date,
                )
            )

    # llama-cpp-python PyPI package
    current_py_ver = ver.get("LLAMA_CPP_VERSION")
    if current_py_ver:
        try:
            latest = latest_pypi_version("llama-cpp-python")
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="python", name="llama-cpp-python[server]",
                    source_file=DOCKER_COMPOSE_LLAMA_PY, current=current_py_ver,
                    latest=latest, applyable=is_newer(latest, current_py_ver),
                    reason="PyPI",
                )
            )

    # vLLM Stack — check Docker Hub for latest <semver>-cu129-ubuntu2404 tag
    current_vllm = ver.get("VLLM_VERSION")
    if current_vllm:
        try:
            tags = docker_hub_tags("vllm/vllm-openai")
            cuda_tags = [t for t in tags if re.match(r"^v?\d+\.\d+\.\d+-cu\d+-ubuntu\d+$", t)]
            latest = sorted(cuda_tags, key=version_key)[-1] if cuda_tags else None
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="docker", name="vllm/vllm-openai (CUDA)",
                    source_file=DOCKERFILE_VLLM, current=current_vllm,
                    latest=latest, applyable=is_newer(latest, current_vllm),
                    reason="Docker Hub <semver>-cu*-ubuntu* tag",
                )
            )

    # HUGGINGFACE_HUB_VERSION (PyPI)
    current_hf = ver.get("HUGGINGFACE_HUB_VERSION")
    if current_hf:
        try:
            latest = latest_pypi_version("huggingface_hub")
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="python", name="huggingface_hub", source_file=DOCKERFILE_VLLM,
                    current=current_hf, latest=latest, applyable=is_newer(latest, current_hf),
                    reason="PyPI",
                )
            )

    # LiteLLM — check PyPI for latest stable version (no pre-releases)
    current_litellm = ver.get("LITELLM_VERSION")
    if current_litellm:
        try:
            latest = latest_pypi_version("litellm")
            if latest and re.search(r"(rc|dev|a|b|alpha|beta)", latest, re.I):
                latest = None
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="docker", name="ghcr.io/berriai/litellm",
                    source_file=DOCKER_COMPOSE_VLLM_GATEWAY, current=current_litellm,
                    latest=latest, applyable=is_newer(latest, current_litellm),
                    reason="PyPI (stable only)",
                )
            )

    return items


def discover_requirements_updates() -> List[UpdateItem]:
    items: List[UpdateItem] = []
    lines = REQ_DEV.read_text(encoding="utf-8").splitlines()
    for line in lines:
        pkg, op, current = parse_requirements_line(line)
        if not pkg:
            continue
        try:
            latest = latest_pypi_version(pkg)
        except error.URLError:
            continue
        if not latest:
            continue

        if op in ("==", ">="):
            applyable = is_newer(latest, current)
            items.append(
                UpdateItem(
                    kind="python",
                    name=pkg,
                    source_file=REQ_DEV,
                    current=current,
                    latest=latest,
                    applyable=applyable,
                    reason="PyPI",
                )
            )
        elif op == "complex":
            items.append(
                UpdateItem(
                    kind="python",
                    name=pkg,
                    source_file=REQ_DEV,
                    current=current,
                    latest=latest,
                    applyable=False,
                    reason="Complex constraint in requirements-dev.txt",
                )
            )
    return items


def build_replacements(items: Sequence[UpdateItem]) -> List[Replacement]:
    replacements: List[Replacement] = []

    for item in items:
        if not item.applyable:
            continue

        if item.name == "ollama/ollama":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_OLLAMA,
                    old=r"${OLLAMA_VERSION:-" + item.current + "}",
                    new=r"${OLLAMA_VERSION:-" + item.latest + "}",
                )
            )
        elif item.name == "mintplexlabs/anythingllm":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_ANYTHING,
                    old=r"${ANYTHINGLLM_VERSION:-" + item.current + "}",
                    new=r"${ANYTHINGLLM_VERSION:-" + item.latest + "}",
                )
            )
        elif item.name == "ghcr.io/open-webui/open-webui":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_OPENWEBUI,
                    old=r"${OW_VERSION:-" + item.current + "}",
                    new=r"${OW_VERSION:-" + item.latest + "}",
                )
            )
        elif item.name == "falkordb/falkordb":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_FALKORDB,
                    old=r"${FALKORDB_VERSION:-" + item.current + "}",
                    new=r"${FALKORDB_VERSION:-" + item.latest + "}",
                )
            )
        elif item.name == "falkordb/mcpserver":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_FALKORDB_MCP,
                    old=r"${FALKORDB_MCP_VERSION:-" + item.current + "}",
                    new=r"${FALKORDB_MCP_VERSION:-" + item.latest + "}",
                )
            )
        elif item.name == "unsloth/unsloth":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_UNSLOTH,
                    old=r"${UNSLOTH_VERSION:-" + item.current + "}",
                    new=r"${UNSLOTH_VERSION:-" + item.latest + "}",
                )
            )
        elif item.name.startswith("ghcr.io/ggml-org/llama.cpp:"):
            # Read actual current tag from each file (they may differ)
            native_text = DOCKER_COMPOSE_LLAMA_NATIVE.read_text(encoding="utf-8") if DOCKER_COMPOSE_LLAMA_NATIVE.exists() else ""
            py_text = DOCKER_COMPOSE_LLAMA_PY.read_text(encoding="utf-8") if DOCKER_COMPOSE_LLAMA_PY.exists() else ""
            dockerfile_text = DOCKERFILE_LLAMA_PY.read_text(encoding="utf-8") if DOCKERFILE_LLAMA_PY.exists() else ""

            # Native server image (10-llamacpp-native.yml)
            m_native = re.search(r"LLAMA_CPP_IMAGE:-ghcr\.io/ggml-org/llama\.cpp:([^\}]+)", native_text)
            if m_native:
                replacements.append(
                    Replacement(
                        source_file=DOCKER_COMPOSE_LLAMA_NATIVE,
                        old=r"${LLAMA_CPP_IMAGE:-ghcr.io/ggml-org/llama.cpp:" + m_native.group(1) + "}",
                        new=r"${LLAMA_CPP_IMAGE:-ghcr.io/ggml-org/llama.cpp:" + item.latest + "}",
                    )
                )

            # Python server build arg (20-llamacpp-py.yml)
            m_py = re.search(r"BASE_IMAGE:-ghcr\.io/ggml-org/llama\.cpp:([^\}]+)", py_text)
            if m_py:
                replacements.append(
                    Replacement(
                        source_file=DOCKER_COMPOSE_LLAMA_PY,
                        old=r"${BASE_IMAGE:-ghcr.io/ggml-org/llama.cpp:" + m_py.group(1) + "}",
                        new=r"${BASE_IMAGE:-ghcr.io/ggml-org/llama.cpp:" + item.latest + "}",
                    )
                )

            # Dockerfile base image ARG
            m_df = re.search(r"ARG BASE_IMAGE=ghcr\.io/ggml-org/llama\.cpp:(\S+)", dockerfile_text)
            if m_df:
                replacements.append(
                    Replacement(
                        source_file=DOCKERFILE_LLAMA_PY,
                        old=r"ARG BASE_IMAGE=ghcr.io/ggml-org/llama.cpp:" + m_df.group(1),
                        new=r"ARG BASE_IMAGE=ghcr.io/ggml-org/llama.cpp:" + item.latest,
                    )
                )
        elif item.name == "llama-cpp-python[server]":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_LLAMA_PY,
                    old=r"${LLAMA_CPP_VERSION:-" + item.current + "}",
                    new=r"${LLAMA_CPP_VERSION:-" + item.latest + "}",
                )
            )
            replacements.append(
                Replacement(
                    source_file=DOCKERFILE_LLAMA_PY,
                    old=r"ARG LLAMA_CPP_VERSION=" + item.current,
                    new=r"ARG LLAMA_CPP_VERSION=" + item.latest,
                )
            )
        elif item.name == "vllm/vllm-openai (CUDA)":
            # Update Dockerfile ARG (read actual current from file)
            df_text = DOCKERFILE_VLLM.read_text(encoding="utf-8") if DOCKERFILE_VLLM.exists() else ""
            m_vllm = re.search(r"ARG VLLM_VERSION=(\S+)", df_text)
            if m_vllm:
                replacements.append(
                    Replacement(
                        source_file=DOCKERFILE_VLLM,
                        old=f"ARG VLLM_VERSION={m_vllm.group(1)}",
                        new=f"ARG VLLM_VERSION={item.latest}",
                    )
                )

            # Update compose file build arg/image fallback defaults
            if DOCKER_COMPOSE_VLLM_ENGINE_BASE.exists():
                base_text = DOCKER_COMPOSE_VLLM_ENGINE_BASE.read_text(encoding="utf-8")
                m_base_vllm = re.search(r"VLLM_VERSION: \$\{VLLM_VERSION:-([^}]+)\}", base_text)
                if m_base_vllm:
                    replacements.append(
                        Replacement(
                            source_file=DOCKER_COMPOSE_VLLM_ENGINE_BASE,
                            old=f"VLLM_VERSION: ${{VLLM_VERSION:-{m_base_vllm.group(1)}}}",
                            new=f"VLLM_VERSION: ${{VLLM_VERSION:-{item.latest}}}",
                        )
                    )
                m_img = re.search(r"image: llama-infra-vllm:(\S+)", base_text)
                if m_img:
                    replacements.append(
                        Replacement(
                            source_file=DOCKER_COMPOSE_VLLM_ENGINE_BASE,
                            old=f"image: llama-infra-vllm:{m_img.group(1)}",
                            new=f"image: llama-infra-vllm:{item.latest}",
                        )
                    )

        elif item.name == "huggingface_hub":
            # Update Dockerfile ARG (read actual current from file)
            df_text = DOCKERFILE_VLLM.read_text(encoding="utf-8") if DOCKERFILE_VLLM.exists() else ""
            m_hf = re.search(r"ARG HUGGINGFACE_HUB_VERSION=(\S+)", df_text)
            if m_hf:
                replacements.append(
                    Replacement(
                        source_file=DOCKERFILE_VLLM,
                        old=f"ARG HUGGINGFACE_HUB_VERSION={m_hf.group(1)}",
                        new=f"ARG HUGGINGFACE_HUB_VERSION={item.latest}",
                    )
                )

        elif item.name == "ghcr.io/berriai/litellm":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_VLLM_GATEWAY,
                    old=r"${LITELLM_VERSION:-" + item.current + "}",
                    new=r"${LITELLM_VERSION:-" + item.latest + "}",
                )
            )

        elif item.source_file == REQ_DEV:
            # Keep existing operator style while bumping version constraints.
            file_text = REQ_DEV.read_text(encoding="utf-8")
            op = "==" if f"{item.name}=={item.current}" in file_text else ">="
            replacements.append(
                Replacement(
                    source_file=REQ_DEV,
                    old=f"{item.name}{op}{item.current}",
                    new=f"{item.name}{op}{item.latest}",
                )
            )

    return replacements


def apply_replacements(
    preview_only: bool, replacements: Sequence[Replacement]
) -> Dict[Path, str]:
    by_file: Dict[Path, List[Replacement]] = {}
    for rep in replacements:
        by_file.setdefault(rep.source_file, []).append(rep)

    updated_text: Dict[Path, str] = {}
    for file_path, reps in by_file.items():
        if file_path == REQ_FROZEN:
            raise RuntimeError("Refusing to edit frozen workspace/requirements.txt")

        original = file_path.read_text(encoding="utf-8")
        changed = original
        for rep in reps:
            changed = changed.replace(rep.old, rep.new)

        if changed != original:
            diff = "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    changed.splitlines(keepends=True),
                    fromfile=str(file_path),
                    tofile=str(file_path),
                )
            )
            print(diff)
            updated_text[file_path] = changed

    if not preview_only:
        for file_path, text in updated_text.items():
            file_path.write_text(text, encoding="utf-8")

    return updated_text


def discover_all_updates() -> List[UpdateItem]:
    docker_items = discover_docker_updates()
    req_items = discover_requirements_updates()
    all_items = docker_items + req_items
    return [i for i in all_items if i.current != i.latest]


def print_update_report(items: Sequence[UpdateItem]) -> None:
    if not items:
        print("No update targets discovered.")
        return

    print("Discovered update targets:")
    for item in items:
        marker = "UPDATE" if item.applyable else "INFO"
        date_str = f" [{item.date}]" if item.date else ""
        print(
            f"- [{marker}] {item.kind:<6} {item.name:<40} "
            f"{item.current} -> {item.latest}{date_str} ({item.reason})"
        )


def write_proposal(path: Path, items: Sequence[UpdateItem]) -> None:
    payload = {
        "generated_by": "tools/update_manager.py",
        "items": [
            {
                "kind": i.kind,
                "name": i.name,
                "source_file": str(i.source_file.relative_to(ROOT)),
                "current": i.current,
                "latest": i.latest,
                "applyable": i.applyable,
                "reason": i.reason,
            }
            for i in items
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote proposal: {path}")


def generate_changelog_entry(items: Sequence[UpdateItem]) -> str:
    """Generate a changelog entry for Docker image version bumps."""
    from datetime import datetime

    today = datetime.now().strftime("%B %d, %Y")

    lines = []
    lines.append(f"## Docker Image Updates - {today}\n")
    lines.append("**Note:** Each update was manually approved by the user via interactive prompt.\n")
    lines.append("")

    docker_items = [i for i in items if i.kind == "docker" and i.applyable]
    python_items = [i for i in items if i.kind == "python" and i.applyable]

    if docker_items:
        lines.append("### Updated Docker Images\n")
        for item in docker_items:
            lines.append(f"- **{item.name}**: `{item.current}` → `{item.latest}`")
        lines.append("")

    if python_items:
        lines.append("### Updated Python Packages\n")
        for item in python_items:
            lines.append(f"- **{item.name}**: `{item.current}` → `{item.latest}`")
        lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def update_changelog(items: Sequence[UpdateItem]) -> None:
    """Add a changelog entry for the updates."""
    changelog_path = ROOT / "CHANGELOG.md"
    entry = generate_changelog_entry(items)

    if not changelog_path.exists():
        print(f"Warning: CHANGELOG.md not found at {changelog_path}")
        return

    # Read existing content
    original = changelog_path.read_text(encoding="utf-8")

    # Check if we already have an entry for today
    today_pattern = datetime.now().strftime("%B %d, %Y")
    if f"## Docker Image Updates - {today_pattern}" in original:
        # Update existing entry - insert before the next section
        lines = original.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if line.startswith("## ") and f"Docker Image Updates - {today_pattern}" not in line:
                insert_idx = i
                break
        if insert_idx is None:
            insert_idx = len(lines)

        lines.insert(insert_idx, entry.rstrip())
        new_content = "\n".join(lines)
    else:
        # Insert after the header but before the first section
        lines = original.split("\n")
        insert_idx = 1 if lines[0].startswith("#") else 0
        lines.insert(insert_idx, entry)
        new_content = "\n".join(lines)

    if new_content != original:
        changelog_path.write_text(new_content, encoding="utf-8")
        print(f"Updated CHANGELOG.md")


def interactive_confirm() -> bool:
    answer = input("Apply these updates? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def run_check(args: argparse.Namespace) -> int:
    items = discover_all_updates()
    print_update_report(items)
    return 0


def run_suggest(args: argparse.Namespace) -> int:
    items = discover_all_updates()
    print_update_report(items)
    write_proposal(Path(args.proposal), items)
    return 0


def run_apply(args: argparse.Namespace) -> int:
    items = discover_all_updates()
    print_update_report(items)

    to_apply = [i for i in items if i.applyable]
    if not to_apply:
        print("No applicable updates found.")
        return 0

    replacements = build_replacements(to_apply)
    if not replacements:
        print("No replacements generated.")
        return 0

    print("\nPlanned file changes:\n")
    apply_replacements(preview_only=True, replacements=replacements)

    if not args.yes and not interactive_confirm():
        print("Cancelled. No files were modified.")
        return 0

    updated = apply_replacements(preview_only=False, replacements=replacements)

    # Collect VERSIONS.env updates from docker/python items (not requirements-dev.txt)
    versions_updates: Dict[str, str] = {}
    for item in to_apply:
        if item.source_file == REQ_DEV:
            continue  # Python packages go through requirements-dev.txt only
        var_name = None
        if item.name == "ollama/ollama": var_name = "OLLAMA_VERSION"
        elif item.name == "mintplexlabs/anythingllm": var_name = "ANYTHINGLLM_VERSION"
        elif item.name == "ghcr.io/open-webui/open-webui": var_name = "OW_VERSION"
        elif item.name == "falkordb/falkordb": var_name = "FALKORDB_VERSION"
        elif item.name == "falkordb/mcpserver": var_name = "FALKORDB_MCP_VERSION"
        elif item.name == "unsloth/unsloth": var_name = "UNSLOTH_VERSION"
        elif item.name.startswith("ghcr.io/ggml-org/llama.cpp:"): var_name = "LLAMA_CPP_IMAGE"
        elif item.name == "llama-cpp-python[server]": var_name = "LLAMA_CPP_VERSION"
        elif item.name == "vllm/vllm-openai (CUDA)": var_name = "VLLM_VERSION"
        elif item.name == "huggingface_hub": var_name = "HUGGINGFACE_HUB_VERSION"
        elif item.name == "ghcr.io/berriai/litellm": var_name = "LITELLM_VERSION"

        if var_name:
            versions_updates[var_name] = item.latest

    if versions_updates and VERSIONS_ENV.exists():
        _write_versions_env(versions_updates)
        print(f"Updated VERSIONS.env")

    if updated:
        print(f"Applied updates to {len(updated)} file(s).")
        # Update changelog with the updates
        update_changelog(to_apply)
    else:
        print("Nothing changed after replacement pass.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update manager for docker tags and packages"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="List current and latest versions")
    p_check.set_defaults(func=run_check)

    p_suggest = sub.add_parser("suggest", help="List updates and write proposal JSON")
    p_suggest.add_argument("--proposal", default=str(DEFAULT_PROPOSAL))
    p_suggest.set_defaults(func=run_suggest)

    p_apply = sub.add_parser("apply", help="Show diff and apply after confirmation")
    p_apply.add_argument("--yes", action="store_true", help="Skip prompt and apply")
    p_apply.set_defaults(func=run_apply)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except error.HTTPError as exc:
        print(f"HTTP error while fetching versions: {exc}", file=sys.stderr)
        return 2
    except error.URLError as exc:
        print(f"Network error while fetching versions: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Update manager failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
