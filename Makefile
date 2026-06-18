SHELL := /bin/bash
.DEFAULT_GOAL := help

# load .env file if it exists
-include .env
export

COMPOSE_CORE := docker compose --project-directory $(CURDIR) \
	-f compose/main/00-networks-and-volumes.yml \
	-f compose/main/10-ollama.yml \
	-f compose/main/20-anythingllm.yml \
	-f compose/main/30-open-webui.yml
COMPOSE_OLLAMA := docker compose --project-directory $(CURDIR) \
	-f compose/main/00-networks-and-volumes.yml \
	-f compose/main/10-ollama.yml
COMPOSE_FALKOR := docker compose --project-directory $(CURDIR) \
	-f compose/main/00-networks-and-volumes.yml \
	-f compose/main/40-falkordb.yml \
	-f compose/main/50-falkordb-mcp.yml
COMPOSE_UNSLOTH := docker compose --project-directory $(CURDIR) \
	-f compose/main/00-networks-and-volumes.yml \
	-f compose/main/60-unsloth.yml
COMPOSE_MAIN := docker compose --project-directory $(CURDIR) \
	-f compose/main/00-networks-and-volumes.yml \
	-f compose/main/10-ollama.yml \
	-f compose/main/20-anythingllm.yml \
	-f compose/main/30-open-webui.yml \
	-f compose/main/40-falkordb.yml \
	-f compose/main/50-falkordb-mcp.yml \
	-f compose/main/60-unsloth.yml
COMPOSE_LLAMA := docker compose --project-directory $(CURDIR) -f docker-compose.llama.cpp.yml
LLAMA_CPP_IMAGE ?= ghcr.io/ggml-org/llama.cpp:full-cuda-b5350

.PHONY: help help-verbose \
	config-main config-falkor config-llama config-all \
	config-unsloth config-open-webui \
	pull-main pull-ollama pull-open-webui pull-falkor pull-falkordb pull-falkordb-mcp pull-unsloth pull-llama pull-all \
	build-llamacpp build-llamacpp-py models-sync \
	updates-check updates-suggest updates-apply \
	check-agent-docs verify-agent-routing check-doc-links \
	precommit-install precommit-run precommit-update \
	up-ollama up-anythingllm up-open-webui up-main up-falkordb up-falkordb-mcp up-unsloth up-main-all \
	up-llamacpp up-llamacpp-py up-llama \
	down-main down-falkor down-falkordb down-falkordb-mcp down-unsloth down-llama down-all \
	restart-ollama restart-anythingllm restart-open-webui restart-falkordb restart-falkordb-mcp restart-unsloth restart-llamacpp restart-llamacpp-py \
	logs-ollama logs-anythingllm logs-open-webui logs-falkordb logs-falkordb-mcp logs-unsloth logs-llamacpp logs-llamacpp-py logs-all \
	ps-main ps-falkor ps-falkordb ps-falkordb-mcp ps-unsloth ps-llama ps-all \
	gpu-host gpu-smoke-llamacpp perf-test clean prune

help:
	@printf "\nllama_infra utility targets\n\n"
	@printf "Main stack:\n"

help-verbose:
	@printf "\nllama_infra utility targets\n\n"
	@printf "Main stack:\n"
	@printf "  make pull-ollama         # Pull Ollama image\n"
	@printf "  make pull-open-webui     # Pull Open WebUI image\n"
	@printf "  make up-ollama           # Start Ollama only\n"
	@printf "  make up-anythingllm      # Start AnythingLLM (and Ollama dependency)\n"
	@printf "  make up-open-webui       # Start Open WebUI (and Ollama dependency)\n"
	@printf "  make up-main             # Start Ollama + AnythingLLM + Open WebUI\n"
	@printf "  make up-falkordb         # Start local FalkorDB service\n"
	@printf "  make up-falkordb-mcp     # Start FalkorDB MCP server (depends on FalkorDB)\n"
	@printf "  make up-unsloth          # Start Unsloth container (GPU + Jupyter/API)\n"
	@printf "  make up-main-all         # Start core stack + FalkorDB + FalkorDB MCP\n"
	@printf "  make down-main           # Stop the main stack\n"
	@printf "  make down-falkordb       # Stop FalkorDB only\n"
	@printf "  make down-falkordb-mcp   # Stop FalkorDB MCP only\n"
	@printf "  make down-falkor         # Stop FalkorDB + MCP stack\n"
	@printf "  make down-unsloth        # Stop Unsloth stack\n"
	@printf "\nllama.cpp stack:\n"
	@printf "  make up-llamacpp         # Start the native llama.cpp server\n"
	@printf "  make build-llamacpp      # Build the native llama.cpp server image\n"
	@printf "  make build-llamacpp-py   # Build the python llama-cpp server image\n"
	@printf "  make up-llamacpp-py      # Start the python llama-cpp server\n"
	@printf "  make down-llama          # Stop the llama.cpp stack\n"
	@printf "\nBenchmarks:\n"
	@printf "  make perf-test [ARGS='--model foo --iterations 5']\n"
	@printf "                        # Run performance tests (pass extra args via ARGS)\n"
	@printf "\nNamed benchmark targets (with regression comparison):\n"
	@printf "  make perf-test-planner       # Benchmark planner model   → benchmarks/planner/\n"
	@printf "  make perf-test-coder         # Benchmark coder model     → benchmarks/coder/\n"
	@printf "  make perf-test-fast-coder    # Benchmark fast-coder model\n"
	@printf "                        # Compares against reg-results.json in the output dir.\n"
	@printf "                        # Warmup is skipped; only last measured run per combo\n"
	@printf "                        # serves as baseline when no reference exists yet.\n"
	@printf "\nDiagnostics:\n"
	@printf "  make config-all          # Render both compose files\n"
	@printf "  make pull-all            # Pull all pinned images\n"
	@printf "  make ps-falkordb         # Show FalkorDB container status\n"
	@printf "  make ps-falkordb-mcp     # Show FalkorDB MCP container status\n"
	@printf "  make ps-unsloth          # Show Unsloth container status\n"
	@printf "  make ps-all              # Show running containers in both stacks\n"
	@printf "  make logs-all            # Tail logs from all containers\n"
	@printf "  make models-sync         # Sync models from workspace/models/models-config.yaml inside ollama-server\n"
	@printf "  make gpu-host            # Show host NVIDIA status\n"
	@printf "  make gpu-smoke-llamacpp  # Run a CUDA image smoke test with nvidia-smi\n"
	@printf "\nUpdate manager:\n"
	@printf "  make updates-check       # Check latest Docker tags and Python package versions\n"
	@printf "  make updates-suggest     # Check and write .update-manager-proposal.json\n"
	@printf "  make updates-apply       # Show diff and apply after interactive prompt\n"
	@printf "\nCode quality:\n"
	@printf "  make check-agent-docs    # Validate required headings in .github/agents/*.md\n"
	@printf "  make verify-agent-routing # Run agent docs checker + unit tests\n"
	@printf "  make check-doc-links     # Verify all local markdown links in README and docs/ resolve\n"
	@printf "  make precommit-install   # Install pre-commit git hooks\n"
	@printf "  make precommit-run       # Run all pre-commit hooks on all files\n"
	@printf "  make precommit-update    # Update pinned hook revisions in .pre-commit-config.yaml\n"
	@printf "\nCleanup:\n"
	@printf "  make clean               # Remove temporary files\n"
	@printf "  make prune               # Prune Docker system and volumes\n"
	@printf "\nOverride examples:\n"
	@printf "  OLLAMA_VERSION=0.18.2 make config-main\n"
	@printf "  UNSLOTH_VERSION=2026.5.9-pt2.10.0-vllm-0.16.0-cu12.8-studio-release-v0.1.43-beta-2026-MAY-31 make pull-unsloth\n"
	@printf "  IMAGE=ghcr.io/ggml-org/llama.cpp:full-cuda-b5343 make config-llama\n"
	@printf "  LLAMA_CPP_VERSION=0.3.18 REQUIREMENTS_FILE=requirements-dev.txt make build-llamacpp-py\n\n"
	@printf "Environment variables (set in .env):\n"
	@printf "  OLLAMA_VERSION         : 0.30.9\n"
	@printf "  ANYTHINGLLM_VERSION    : 1.14.1\n"
	@printf "  OW_VERSION             : v0.8.11\n"
	@printf "  FALKORDB_VERSION       : v4.18.10\n"
	@printf "  FALKORDB_MCP_VERSION   : 1.2.2\n"
	@printf "  UNSLOTH_VERSION        : 2026.5.9-pt2.10.0-vllm-0.16.0-cu12.8-studio-release-v0.1.43-beta-2026-MAY-31\n"
	@printf "  IMAGE                  : ghcr.io/ggml-org/llama.cpp:full-cuda-b5350\n"
	@printf "  LLAMA_CPP_VERSION      : 0.3.30\n"
	@printf "  DATA_DIR               : ./data\n"
	@printf "  REGISTRY               : llamacpp-server-python\n"
	@printf "  GPU_ID                 : 0\n"
	@printf "  MODELS                 : ./models\n"

config-main:
	$(COMPOSE_CORE) config

config-falkor:
	$(COMPOSE_FALKOR) config

config-unsloth:
	$(COMPOSE_UNSLOTH) config

config-llama:
	$(COMPOSE_LLAMA) config

config-open-webui:
	$(COMPOSE_CORE) config open-webui

config-all: config-main config-falkor config-unsloth config-llama config-open-webui

pull-main:
	$(COMPOSE_CORE) pull

pull-ollama:
	$(COMPOSE_OLLAMA) pull

pull-open-webui:
	$(COMPOSE_CORE) pull open-webui

pull-falkordb:
	$(COMPOSE_FALKOR) pull falkordb

pull-falkordb-mcp:
	$(COMPOSE_FALKOR) pull falkordb-mcpserver

pull-falkor:
	$(COMPOSE_FALKOR) pull

pull-llama:
	$(COMPOSE_LLAMA) pull llamacpp-server

pull-llamacpp:
	$(COMPOSE_LLAMA) pull llamacpp-server

pull-llamacpp-py:
	$(COMPOSE_LLAMA) pull llamacpp-server-py

pull-all: pull-main pull-falkor pull-unsloth pull-llama pull-open-webui

build-llamacpp:
	$(COMPOSE_LLAMA) build llamacpp-server

build-llamacpp-py:
	$(COMPOSE_LLAMA) build llamacpp-server-py

models-sync:
	$(COMPOSE_CORE) run --rm --no-deps ollama-server --sync-only

updates-check:
	python3 tools/update_manager.py check

updates-suggest:
	python3 tools/update_manager.py suggest

updates-apply:
	python3 tools/update_manager.py apply

check-agent-docs:
	python3 tools/check_agent_docs.py

verify-agent-routing: check-agent-docs
	python3 -m pytest -q tests/test_agent_docs_check.py

check-doc-links:
	python3 tools/check_doc_links.py

precommit-install:
	pre-commit install

precommit-run:
	pre-commit run --all-files

precommit-update:
	pre-commit autoupdate

up-ollama:
	@docker start ollama-server >/dev/null 2>&1 || $(COMPOSE_OLLAMA) up -d --no-deps ollama-server

up-anythingllm:
	$(COMPOSE_CORE) up -d anythingllm

up-open-webui:
	$(COMPOSE_CORE) up -d open-webui

up-main:
	$(COMPOSE_CORE) up -d ollama-server anythingllm open-webui

up-falkordb:
	$(COMPOSE_FALKOR) up -d falkordb

up-falkordb-mcp:
	$(COMPOSE_FALKOR) up -d falkordb-mcpserver

up-unsloth:
	$(COMPOSE_UNSLOTH) up -d unsloth-server

up-main-all:
	$(COMPOSE_MAIN) up -d ollama-server anythingllm open-webui falkordb falkordb-mcpserver unsloth-server

up-llamacpp:
	$(COMPOSE_LLAMA) up -d llamacpp-server

up-llamacpp-py:
	$(COMPOSE_LLAMA) up -d llamacpp-server-py

up-llama:
	$(COMPOSE_LLAMA) up -d llamacpp-server llamacpp-server-py

down-main:
	$(COMPOSE_CORE) down

down-falkordb:
	$(COMPOSE_FALKOR) down falkordb

down-falkordb-mcp:
	$(COMPOSE_FALKOR) down falkordb-mcpserver

down-falkor:
	$(COMPOSE_FALKOR) down

down-unsloth:
	$(COMPOSE_UNSLOTH) down

down-llama:
	$(COMPOSE_LLAMA) down

down-all: down-main down-falkordb down-falkordb-mcp down-unsloth down-llama

restart-ollama:
	$(COMPOSE_CORE) restart ollama-server

restart-anythingllm:
	$(COMPOSE_CORE) restart anythingllm

restart-open-webui:
	$(COMPOSE_CORE) restart open-webui

restart-falkordb:
	$(COMPOSE_FALKOR) restart falkordb

restart-falkordb-mcp:
	$(COMPOSE_FALKOR) restart falkordb-mcpserver

restart-unsloth:
	$(COMPOSE_UNSLOTH) restart unsloth-server

restart-llamacpp:
	$(COMPOSE_LLAMA) restart llamacpp-server

restart-llamacpp-py:
	$(COMPOSE_LLAMA) restart llamacpp-server-py

logs-ollama:
	$(COMPOSE_CORE) logs -f --tail=200 ollama-server

logs-anythingllm:
	$(COMPOSE_CORE) logs -f --tail=200 anythingllm

logs-open-webui:
	$(COMPOSE_CORE) logs -f --tail=200 open-webui

logs-falkordb:
	$(COMPOSE_FALKOR) logs -f --tail=200 falkordb

logs-falkordb-mcp:
	$(COMPOSE_FALKOR) logs -f --tail=200 falkordb-mcpserver

logs-unsloth:
	$(COMPOSE_UNSLOTH) logs -f --tail=200 unsloth-server

logs-llamacpp:
	$(COMPOSE_LLAMA) logs -f --tail=200 llamacpp-server

logs-llamacpp-py:
	$(COMPOSE_LLAMA) logs -f --tail=200 llamacpp-server-py

ps-main:
	$(COMPOSE_CORE) ps

ps-falkordb:
	$(COMPOSE_FALKOR) ps falkordb

ps-falkordb-mcp:
	$(COMPOSE_FALKOR) ps falkordb-mcpserver

ps-falkor:
	$(COMPOSE_FALKOR) ps

ps-unsloth:
	$(COMPOSE_UNSLOTH) ps

ps-llama:
	$(COMPOSE_LLAMA) ps

ps-all: ps-main ps-falkordb ps-falkordb-mcp ps-unsloth ps-llama

logs-all:
	@printf "Tailing logs from all containers...\n"
	$(COMPOSE_MAIN) logs -f --tail=100 2>/dev/null || true
	$(COMPOSE_LLAMA) logs -f --tail=100 2>/dev/null || true

perf-test:
	@echo "Running performance tests..." >&2
	scripts/perf_test.sh $(ARGS)

gpu-host:
	nvidia-smi

gpu-smoke-llamacpp:
	docker run --rm --gpus all --entrypoint nvidia-smi $(LLAMA_CPP_IMAGE)

# ── Named benchmark targets ───────────────────────────────────────────────────

# Named benchmark targets — model_flavor is a key (planner/coder/fast-coder),
# not an Ollama model ID. bench.sh maps it to the correct model.

perf-test-planner:
	@mkdir -p benchmarks/planner
	scripts/bench.sh planner --output-dir benchmarks/planner $(ARGS)

perf-test-coder:
	@mkdir -p benchmarks/coder
	scripts/bench.sh coder --output-dir benchmarks/coder $(ARGS)

perf-test-fast-coder:
	@mkdir -p benchmarks/perf-test-fast-coder
	scripts/bench.sh fast-coder --output-dir benchmarks/perf-test-fast-coder $(ARGS)

clean:
	@find . -maxdepth 1 -type f \( -name 'compose_*.txt' -o -name '*_checks.json' -o -name 'verification_report.json' \) -print -delete

prune:
	@printf "Pruning Docker system...\n"
	docker system prune -f
	docker volume prune -f
