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
DOCKER_COMPOSE_LLAMA = ROOT / "docker-compose.llama.cpp.yml"
DOCKERFILE_LLAMA_PY = ROOT / "compose/llama/Dockerfile.llamacpp-server-python"
DOCKER_COMPOSE_VLLM_ENGINE_BASE = ROOT / "compose/vllm/05-vllm-engine-base.yml"
DOCKER_COMPOSE_VLLM_GATEWAY = ROOT / "compose/vllm/40-vllm-gateway.yml"
DOCKERFILE_VLLM = ROOT / "compose/vllm/Dockerfile.vllm"

REQ_DEV = ROOT / "requirements-dev.txt"
REQ_FROZEN = ROOT / "workspace/requirements.txt"


@dataclass
class UpdateItem:
    kind: str
    name: str
    source_file: Path
    current: str
    latest: str
    applyable: bool
    reason: str


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


def is_newer(latest: str, current: str) -> bool:
    full_cuda = re.compile(r"^full-cuda-b(\d+)$")
    latest_m = full_cuda.match(latest)
    current_m = full_cuda.match(current)
    if latest_m and current_m:
        return int(latest_m.group(1)) > int(current_m.group(1))
    return version_key(latest) > version_key(current)


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


def ghcr_tags(namespace_repo: str) -> List[str]:
    token = ghcr_token(namespace_repo)
    data = fetch_json(
        f"https://ghcr.io/v2/{namespace_repo}/tags/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    return data.get("tags", []) or []


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
    items: List[UpdateItem] = []

    ollama_text = DOCKER_COMPOSE_OLLAMA.read_text(encoding="utf-8")
    anything_text = DOCKER_COMPOSE_ANYTHING.read_text(encoding="utf-8")
    openwebui_text = DOCKER_COMPOSE_OPENWEBUI.read_text(encoding="utf-8")
    falkordb_text = DOCKER_COMPOSE_FALKORDB.read_text(encoding="utf-8")
    falkordb_mcp_text = DOCKER_COMPOSE_FALKORDB_MCP.read_text(encoding="utf-8")
    unsloth_text = DOCKER_COMPOSE_UNSLOTH.read_text(encoding="utf-8")
    llama_text = DOCKER_COMPOSE_LLAMA.read_text(encoding="utf-8")

    current_ollama = re.search(r"\$\{OLLAMA_VERSION:-([^}]+)\}", ollama_text)
    current_anything = re.search(r"\$\{ANYTHINGLLM_VERSION:-([^}]+)\}", anything_text)
    current_openwebui = re.search(r"\$\{OW_VERSION:-([^}]+)\}", openwebui_text)
    current_falkordb = re.search(r"\$\{FALKORDB_VERSION:-([^}]+)\}", falkordb_text)
    current_falkordb_mcp = re.search(r"\$\{FALKORDB_MCP_VERSION:-([^}]+)\}", falkordb_mcp_text)
    current_unsloth = re.search(r"\$\{UNSLOTH_VERSION:-([^}]+)\}", unsloth_text)
    current_llama_image = re.search(
        r"\$\{IMAGE:-ghcr\.io/ggml-org/llama\.cpp:([^}]+)\}", llama_text
    )
    current_llama_cpp_ver = re.search(r"\$\{LLAMA_CPP_VERSION:-([^}]+)\}", llama_text)

    if current_ollama:
        try:
            latest = latest_tag(docker_hub_tags("ollama/ollama"), r"^\d+(\.\d+){1,3}$")
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="docker",
                    name="ollama/ollama",
                    source_file=DOCKER_COMPOSE_OLLAMA,
                    current=current_ollama.group(1),
                    latest=latest,
                    applyable=is_newer(latest, current_ollama.group(1)),
                    reason="Docker Hub tag",
                )
            )

    if current_anything:
        try:
            latest = latest_tag(
                docker_hub_tags("mintplexlabs/anythingllm"), r"^\d+(\.\d+){1,3}$"
            )
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="docker",
                    name="mintplexlabs/anythingllm",
                    source_file=DOCKER_COMPOSE_ANYTHING,
                    current=current_anything.group(1),
                    latest=latest,
                    applyable=is_newer(latest, current_anything.group(1)),
                    reason="Docker Hub tag",
                )
            )

    if current_openwebui:
        try:
            latest = latest_tag(
                ghcr_tags("open-webui/open-webui"), r"^v?\d+(\.\d+){1,3}$"
            )
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="docker",
                    name="ghcr.io/open-webui/open-webui",
                    source_file=DOCKER_COMPOSE_OPENWEBUI,
                    current=current_openwebui.group(1),
                    latest=latest,
                    applyable=is_newer(latest, current_openwebui.group(1)),
                    reason="GHCR tag",
                )
            )

    if current_falkordb:
        try:
            latest = latest_tag(docker_hub_tags("falkordb/falkordb"), r"^v?\d+(\.\d+){1,3}$")
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="docker",
                    name="falkordb/falkordb",
                    source_file=DOCKER_COMPOSE_FALKORDB,
                    current=current_falkordb.group(1),
                    latest=latest,
                    applyable=is_newer(latest, current_falkordb.group(1)),
                    reason="Docker Hub tag",
                )
            )

    if current_falkordb_mcp:
        try:
            latest = latest_tag(docker_hub_tags("falkordb/mcpserver"), r"^\d+(\.\d+){1,3}$")
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="docker",
                    name="falkordb/mcpserver",
                    source_file=DOCKER_COMPOSE_FALKORDB_MCP,
                    current=current_falkordb_mcp.group(1),
                    latest=latest,
                    applyable=is_newer(latest, current_falkordb_mcp.group(1)),
                    reason="Docker Hub tag",
                )
            )

    if current_unsloth:
        try:
            latest = latest_tag(docker_hub_tags("unsloth/unsloth"), r"^[0-9]+\.[0-9]+\.[0-9]+.*$")
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="docker",
                    name="unsloth/unsloth",
                    source_file=DOCKER_COMPOSE_UNSLOTH,
                    current=current_unsloth.group(1),
                    latest=latest,
                    applyable=is_newer(latest, current_unsloth.group(1)),
                    reason="Docker Hub tag",
                )
            )

    if current_llama_image:
        try:
            latest = latest_tag(ghcr_tags("ggml-org/llama.cpp"), r"^full-cuda-b\d+$")
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="docker",
                    name="ghcr.io/ggml-org/llama.cpp:full-cuda-b*",
                    source_file=DOCKER_COMPOSE_LLAMA,
                    current=current_llama_image.group(1),
                    latest=latest,
                    applyable=is_newer(latest, current_llama_image.group(1)),
                    reason="GHCR full-cuda-b tag",
                )
            )

    if current_llama_cpp_ver:
        try:
            latest = latest_pypi_version("llama-cpp-python")
        except (error.HTTPError, error.URLError):
            latest = None
        if latest:
            items.append(
                UpdateItem(
                    kind="python",
                    name="llama-cpp-python[server]",
                    source_file=DOCKER_COMPOSE_LLAMA,
                    current=current_llama_cpp_ver.group(1),
                    latest=latest,
                    applyable=is_newer(latest, current_llama_cpp_ver.group(1)),
                    reason="PyPI",
                )
            )

    # vLLM — check Docker Hub for latest <semver>-cu129-ubuntu2404 tag
    if DOCKERFILE_VLLM.exists():
        vllm_text = DOCKERFILE_VLLM.read_text(encoding="utf-8")
        current_vllm = re.search(r"ARG VLLM_VERSION=(v?\d+\.\d+\.\d+-cu\d+-ubuntu\d+)", vllm_text)
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
                        kind="docker",
                        name="vllm/vllm-openai (CUDA)",
                        source_file=DOCKERFILE_VLLM,
                        current=current_vllm.group(1),
                        latest=latest,
                        applyable=is_newer(latest, current_vllm.group(1)),
                        reason="Docker Hub <semver>-cu*-ubuntu* tag",
                    )
                )

    # LiteLLM — check PyPI for latest stable version (no pre-releases)
    if DOCKER_COMPOSE_VLLM_GATEWAY.exists():
        gw_text = DOCKER_COMPOSE_VLLM_GATEWAY.read_text(encoding="utf-8")
        current_litellm = re.search(r"\$\{LITELLM_VERSION:-([^}]+)\}", gw_text)
        if current_litellm:
            try:
                latest = latest_pypi_version("litellm")
                # Skip pre-releases (rc, dev, a, b, alpha, beta)
                if latest and re.search(r"(rc|dev|a|b|alpha|beta)", latest, re.I):
                    latest = None
            except (error.HTTPError, error.URLError):
                latest = None
            if latest:
                items.append(
                    UpdateItem(
                        kind="docker",
                        name="ghcr.io/berriai/litellm",
                        source_file=DOCKER_COMPOSE_VLLM_GATEWAY,
                        current=current_litellm.group(1),
                        latest=latest,
                        applyable=is_newer(latest, current_litellm.group(1)),
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
        elif op == "":
            items.append(
                UpdateItem(
                    kind="python",
                    name=pkg,
                    source_file=REQ_DEV,
                    current="(unpinned)",
                    latest=latest,
                    applyable=False,
                    reason="Unpinned in requirements-dev.txt",
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
        elif item.name == "ghcr.io/ggml-org/llama.cpp:full-cuda-b*":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_LLAMA,
                    old=r"${IMAGE:-ghcr.io/ggml-org/llama.cpp:" + item.current + "}",
                    new=r"${IMAGE:-ghcr.io/ggml-org/llama.cpp:" + item.latest + "}",
                )
            )
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_LLAMA,
                    old=r"${BASE_IMAGE:-ghcr.io/ggml-org/llama.cpp:"
                    + item.current
                    + "}",
                    new=r"${BASE_IMAGE:-ghcr.io/ggml-org/llama.cpp:"
                    + item.latest
                    + "}",
                )
            )
            replacements.append(
                Replacement(
                    source_file=DOCKERFILE_LLAMA_PY,
                    old=r"ARG BASE_IMAGE=ghcr.io/ggml-org/llama.cpp:" + item.current,
                    new=r"ARG BASE_IMAGE=ghcr.io/ggml-org/llama.cpp:" + item.latest,
                )
            )
        elif item.name == "llama-cpp-python[server]":
            replacements.append(
                Replacement(
                    source_file=DOCKER_COMPOSE_LLAMA,
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
            # Update Dockerfile ARG
            replacements.append(
                Replacement(
                    source_file=DOCKERFILE_VLLM,
                    old=f"ARG VLLM_VERSION={item.current}",
                    new=f"ARG VLLM_VERSION={item.latest}",
                )
            )
            # Update compose file build arg/image fallback defaults
            if DOCKER_COMPOSE_VLLM_ENGINE_BASE.exists():
                base_text = DOCKER_COMPOSE_VLLM_ENGINE_BASE.read_text(encoding="utf-8")
                if f"${{VLLM_VERSION:-{item.current}}}" in base_text:
                    replacements.append(
                        Replacement(
                            source_file=DOCKER_COMPOSE_VLLM_ENGINE_BASE,
                            old=f"VLLM_VERSION: ${{VLLM_VERSION:-{item.current}}}",
                            new=f"VLLM_VERSION: ${{VLLM_VERSION:-{item.latest}}}",
                        )
                    )
                    replacements.append(
                        Replacement(
                            source_file=DOCKER_COMPOSE_VLLM_ENGINE_BASE,
                            old=f"image: llama-infra-vllm:{item.current}",
                            new=f"image: llama-infra-vllm:{item.latest}",
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
    return docker_items + req_items


def print_update_report(items: Sequence[UpdateItem]) -> None:
    if not items:
        print("No update targets discovered.")
        return

    print("Discovered update targets:")
    for item in items:
        marker = "UPDATE" if item.applyable else "INFO"
        print(
            f"- [{marker}] {item.kind:<6} {item.name:<40} "
            f"{item.current} -> {item.latest} ({item.reason})"
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
