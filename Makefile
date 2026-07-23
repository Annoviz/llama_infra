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
COMPOSE_GOTENBERG := docker compose --project-directory $(CURDIR) \
	-f compose/gotenberg/00-networks.yml \
	-f compose/gotenberg/10-gotenberg.yml \
	-f compose/gotenberg/20-gotenberg-mcp.yml
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
	-f compose/main/60-unsloth.yml \
	-f compose/main/70-open-websearch-mcp.yml
COMPOSE_LLAMA := docker compose --project-directory $(CURDIR) \
	-f compose/llama/00-networks-and-volumes.yml \
	-f compose/llama/10-llamacpp-native.yml \
	-f compose/llama/20-llamacpp-py.yml
COMPOSE_LLAMA_ROUTER := docker compose --project-directory $(CURDIR) \
	-f compose/llama/05-llamacpp-router-networks.yml \
	-f compose/llama/15-llamacpp-router.yml \
	-f compose/llama/25-llamacpp-router-gateway.yml
COMPOSE_VLLM := docker compose --project-directory $(CURDIR) \
	-f compose/vllm/00-vllm-networks.yml \
	-f compose/vllm/05-vllm-engine-base.yml \
	-f compose/vllm/10-vllm-planner.yml \
	-f compose/vllm/20-vllm-coder.yml \
	-f compose/vllm/30-vllm-fastcoder.yml \
	-f compose/vllm/40-vllm-gateway.yml
COMPOSE_VLLM_DL := docker compose --project-directory $(CURDIR) \
	-f compose/vllm/00-vllm-networks.yml \
	-f compose/vllm/90-vllm-download.yml
LLAMA_CPP_IMAGE ?= ghcr.io/ggml-org/llama.cpp:full-cuda-b4738

.PHONY: help help-verbose \
	config-main config-falkor config-llama config-llama-router config-vllm config-all \
	config-gotenberg config-unsloth config-open-webui \
	pull-main pull-ollama pull-open-webui pull-falkor pull-falkordb pull-falkordb-mcp pull-gotenberg pull-unsloth pull-llama pull-vllm-base pull-all \
	build-llamacpp-py build-vllm models-sync \
	updates-check updates-suggest updates-apply \
	check-agent-docs verify-agent-routing check-doc-links \
	precommit-install precommit-run precommit-update \
	up-ollama up-anythingllm up-open-webui up-main up-falkordb up-falkordb-mcp up-gotenberg up-unsloth up-main-all up-open-websearch-mcp \
	up-llamacpp up-llamacpp-py up-llama up-llamacpp-router \
	up-vllm up-vllm-planner up-vllm-coder up-vllm-fastcoder download-vllm-models \
	down-main down-gotenberg down-falkor down-falkordb down-falkordb-mcp down-unsloth down-llama down-vllm down-llamacpp-router down-all down-open-websearch-mcp \
	restart-ollama restart-anythingllm restart-open-webui restart-falkordb restart-falkordb-mcp restart-gotenberg restart-unsloth restart-llamacpp restart-llamacpp-py restart-open-websearch-mcp \
	restart-vllm-planner restart-vllm-coder restart-vllm-fastcoder restart-llamacpp-router \
	logs-ollama logs-anythingllm logs-open-webui logs-falkordb logs-falkordb-mcp logs-unsloth logs-llamacpp logs-llamacpp-py logs-all logs-open-websearch-mcp \
	logs-vllm-planner logs-vllm-coder logs-vllm-fastcoder logs-vllm-gateway \
	ps-main ps-falkor ps-falkordb ps-falkordb-mcp ps-unsloth ps-llama ps-vllm ps-all ps-open-websearch-mcp \
	gpu-host gpu-smoke-llamacpp smoke-vllm perf-test vision-test bench-vision model-rebuild clean prune

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
	@printf "  make up-gotenberg        # Start Gotenberg + MCP server for doc-to-PDF conversion\n"
	@printf "  make up-unsloth          # Start Unsloth container (GPU + Jupyter/API)\n"
	@printf "  make up-main-all         # Start core stack + FalkorDB + FalkorDB MCP\n"
	@printf "  make up-open-websearch-mcp # Start Open Web Search MCP server\n"
	@printf "  make down-main           # Stop the main stack\n"
	@printf "  make down-gotenberg      # Stop Gotenberg + MCP server\n"
	@printf "  make down-falkordb       # Stop FalkorDB only\n"
	@printf "  make down-falkordb-mcp   # Stop FalkorDB MCP only\n"
	@printf "  make down-falkor         # Stop FalkorDB + MCP stack\n"
	@printf "  make down-unsloth        # Stop Unsloth stack\n"
	@printf "\nvLLM stack (Ollama replacement — gateway on port 11434):\n"
	@printf "  NOTE: vLLM and Ollama are mutually exclusive (both bind 11434).\n"
	@printf "        Stop Ollama with 'make down-main' before starting vLLM.\n"
	@printf "  make up-vllm             # Build + start all 3 engines + LiteLLM gateway\n"
	@printf "  make up-vllm-planner     # Start planner engine only\n"
	@printf "  make up-vllm-coder       # Start coder engine only\n"
	@printf "  make up-vllm-fastcoder   # Start fastcoder engine only\n"
	@printf "  make down-vllm           # Stop the vLLM stack\n"
	@printf "  make build-vllm          # Build custom vLLM image\n"
	@printf "  make download-vllm-models  # Pre-download HF models to \${MODELS}/vllm/\n"
	@printf "  make config-llama-router # Render llama.cpp router + gateway compose config\n"
	@printf "  make config-vllm         # Render vLLM compose config\n"
	@printf "  make ps-vllm             # Show vLLM container status\n"
	@printf "  make logs-vllm-planner   # Follow planner engine logs\n"
	@printf "  make logs-vllm-coder     # Follow coder engine logs\n"
	@printf "  make logs-vllm-fastcoder # Follow fastcoder engine logs\n"
	@printf "  make logs-vllm-gateway   # Follow gateway (LiteLLM) logs\n"
	@printf "\nllama.cpp stack:\n"
	@printf "  make up-llamacpp         # Start the native llama.cpp server (port: ${LLAMA_CPP_PORT:-8080})\n"
	@printf "  make build-llamacpp-py   # Build the python llama-cpp server image\n"
	@printf "  make up-llamacpp-py      # Start the python llama-cpp server\n"
	@printf "  NOTE: Router mode and Ollama/vLLM are mutually exclusive (both bind 11434).\n"
	@printf "        Stop one before starting another.\n"
	@printf "  make up-llamacpp-router  # Start llama.cpp router mode (multi-model, port: ${LLAMA_ROUTER_PORT:-11434})\n"
	@printf "  make down-llama          # Stop the llama.cpp stack\n"
	@printf "\nBenchmarks:\n"
	@printf "  make perf-test [ARGS='--model foo --iterations 5']\n"
	@printf "                        # Run performance tests (pass extra args via ARGS)\n"
	@printf "\nNamed benchmark targets (with regression comparison):\n"
	@printf "  make perf-test-planner       # Benchmark planner model   → benchmarks/planner/\n"
	@printf "  make perf-test-coder         # Benchmark coder model     → benchmarks/coder/\n"
	@printf "  make perf-test-fast-coder    # Benchmark fast-coder model\n"
	@printf "                        # Compares against reg-results.json in the output dir.\n"
	@printf "\nVision (image understanding) tests:\n"
	@printf "  make vision-test MODEL=fast-coder IMAGE=workspace/data/person.png\n"
	@printf "                        # Test multimodal image understanding of a model\n"
	@printf "  Available images: workspace/data/*.png, *.jpg\n"
	@printf "\nVision benchmarks (structured results + regression):\n"
	@printf "  make bench-vision MODEL=fast-coder IMAGES=img1.jpg,img2.jpg\n"
	@printf "                        # Benchmark vision across models/images → benchmarks/vision/\n"
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
	@printf "  GOTENBERG_IMAGE        : ${GOTENBERG_IMAGE:-gotenberg/gotenberg:8}\n"
	@printf "  UNSLOTH_VERSION        : ${UNSLOTH_VERSION:-2026.5.9-pt2.10.0-vllm-0.16.0-cu12.8-studio-release-v0.1.43-beta-2026-MAY-31}\n"
	@printf "  LLAMA_CPP_IMAGE          : ${LLAMA_CPP_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda13}\n"
	@printf "  LLAMA_CPP_PORT           : 8080\n"
	@printf "  LLAMA_ROUTER_PORT        : 8080 (internal container port)\n"
	@printf "  VLLM_GATEWAY_PORT        : 11434 (Ollama drop-in replacement via LiteLLM gateway)\n"
	@printf "  LLAMA_ROUTER_MODELS_MAX  : 2\n"
	@printf "  LLAMA_CPP_VERSION      : 0.3.30\n"
	@printf "  VLLM_VERSION           : v0.25.0-cu129-ubuntu2404\n"
	@printf "  LITELLM_VERSION        : 1.92.0\n"
	@printf "  HF_DOWNLOADER_VERSION  : 0.1.0\n"
	@printf "  VLLM_GATEWAY_PORT      : 11434\n"
	@printf "  DATA_DIR               : ./data\n"
	@printf "  REGISTRY               : llamacpp-server-python\n"
	@printf "  GPU_ID                 : 0\n"
	@printf "  MODELS                 : ./models\n"

config-main:
	$(COMPOSE_CORE) config

config-gotenberg:
	$(COMPOSE_GOTENBERG) config

config-falkor:
	$(COMPOSE_FALKOR) config

config-unsloth:
	$(COMPOSE_UNSLOTH) config

config-llama:
	$(COMPOSE_LLAMA) config

config-llama-router:
	$(COMPOSE_LLAMA_ROUTER) config

config-open-webui:
	$(COMPOSE_CORE) config open-webui

config-vllm:
	$(COMPOSE_VLLM) config

config-all: config-main config-falkor config-unsloth config-llama config-llama-router config-open-webui config-vllm

# Build (custom Dockerfiles)
build-vllm:
	$(COMPOSE_VLLM) build --pull vllm-planner vllm-coder vllm-fastcoder

# Smoke test — verify compose config + upstream image tag before building
smoke-vllm:
	$(COMPOSE_VLLM) config > /dev/null && echo "compose OK" || (echo "compose FAILED"; exit 1)
	docker pull vllm/vllm-openai:${VLLM_VERSION:-v0.25.0-cu129-ubuntu2404}
	docker pull ghcr.io/berriai/litellm:${LITELLM_VERSION:-1.92.0}

pull-vllm-base:
	docker pull vllm/vllm-openai:${VLLM_VERSION:-v0.25.0-cu129-ubuntu2404}
	docker pull ghcr.io/berriai/litellm:${LITELLM_VERSION:-1.92.0}

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

pull-gotenberg:
	$(COMPOSE_GOTENBERG) pull

pull-falkor:
	$(COMPOSE_FALKOR) pull

pull-llama:
	$(COMPOSE_LLAMA) pull llamacpp-server

pull-llamacpp:
	$(COMPOSE_LLAMA) pull llamacpp-server

pull-llamacpp-py:
	$(COMPOSE_LLAMA) pull llamacpp-server-py

pull-all: pull-main pull-falkor pull-unsloth pull-llama pull-open-webui pull-vllm-base

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
	conda run -n llama_infra python3 -m pytest -q tests/test_agent_docs_check.py

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

up-gotenberg:
	$(COMPOSE_GOTENBERG) up -d gotenberg gotenberg-mcp

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

# llama.cpp router mode — multi-model server on 11434 (mutually exclusive with Ollama/vLLM)
up-llamacpp-router:
	@printf "NOTE: Router binds port 11434 — stop Ollama and vLLM first.\n"
	$(COMPOSE_LLAMA_ROUTER) up -d

down-llamacpp-router:
	$(COMPOSE_LLAMA_ROUTER) down

restart-llamacpp-router:
	$(COMPOSE_LLAMA_ROUTER) restart llamacpp-router

logs-llamacpp-router:
	$(COMPOSE_LLAMA_ROUTER) logs -f --tail=200 llamacpp-router

# vLLM stack — gateway on 11434 (mutually exclusive with Ollama)
up-vllm: build-vllm
	$(COMPOSE_VLLM) up -d

up-vllm-planner: build-vllm
	$(COMPOSE_VLLM) up -d vllm-planner

up-vllm-coder: build-vllm
	$(COMPOSE_VLLM) up -d vllm-coder

up-vllm-fastcoder: build-vllm
	$(COMPOSE_VLLM) up -d vllm-fastcoder

download-vllm-models: build-vllm
	$(COMPOSE_VLLM_DL) --profile download up --remove-orphans

down-main:
	$(COMPOSE_CORE) down

down-gotenberg:
	$(COMPOSE_GOTENBERG) down

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

down-vllm:
	$(COMPOSE_VLLM) down

down-all: down-main down-falkor down-unsloth down-llama down-vllm

restart-ollama:
	$(COMPOSE_CORE) restart ollama-server

restart-anythingllm:
	$(COMPOSE_CORE) restart anythingllm

restart-open-webui:
	$(COMPOSE_CORE) restart open-webui

restart-gotenberg:
	$(COMPOSE_GOTENBERG) restart gotenberg gotenberg-mcp

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

# vLLM restart targets
restart-vllm-planner:
	$(COMPOSE_VLLM) restart vllm-planner

restart-vllm-coder:
	$(COMPOSE_VLLM) restart vllm-coder

restart-vllm-fastcoder:
	$(COMPOSE_VLLM) restart vllm-fastcoder

logs-ollama:
	$(COMPOSE_CORE) logs -f --tail=200 ollama-server

logs-anythingllm:
	$(COMPOSE_CORE) logs -f --tail=200 anythingllm

logs-open-webui:
	$(COMPOSE_CORE) logs -f --tail=200 open-webui

logs-gotenberg:
	$(COMPOSE_GOTENBERG) logs -f --tail=200 gotenberg

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

# vLLM log targets
logs-vllm-planner:
	$(COMPOSE_VLLM) logs -f --tail=200 vllm-planner

logs-vllm-coder:
	$(COMPOSE_VLLM) logs -f --tail=200 vllm-coder

logs-vllm-fastcoder:
	$(COMPOSE_VLLM) logs -f --tail=200 vllm-fastcoder

logs-vllm-gateway:
	$(COMPOSE_VLLM) logs -f --tail=200 vllm-gateway

ps-main:
	$(COMPOSE_CORE) ps

ps-falkordb:
	$(COMPOSE_FALKOR) ps falkordb

ps-falkordb-mcp:
	$(COMPOSE_FALKOR) ps falkordb-mcpserver

ps-gotenberg:
	$(COMPOSE_GOTENBERG) ps

ps-falkor:
	$(COMPOSE_FALKOR) ps

ps-unsloth:
	$(COMPOSE_UNSLOTH) ps

ps-llama:
	$(COMPOSE_LLAMA) ps

ps-vllm:
	$(COMPOSE_VLLM) ps

ps-llamacpp-router:
	$(COMPOSE_LLAMA_ROUTER) ps

ps-all: ps-main ps-gotenberg ps-falkor ps-unsloth ps-llama ps-vllm ps-llamacpp-router

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

# ── Model rebuild ──────────────────────────────────────────────────────────────

model-rebuild:
	@$(COMPOSE_OLLAMA) run --rm --no-deps ollama-server ollama create $(NAME) -f /models/$(NAME).Modelfile


# ── Vision (multimodal image understanding) test ──────────────────────────────

vision-test:
	@python3 scripts/vision_test.py \
		$(IMAGE) \
		--model $(MODEL) \
		--prompt "$(PROMPT)" \
		--max-tokens "$${MAX_TOKENS:-512}" \
		--base-url "$${OLLAMA_BASE_URL:-http://localhost:11434}" \
		--api-format "$${API_FORMAT:-ollama}" \
		--timeout "$${TIMEOUT:-300}"


# ── Vision benchmark (structured results + regression baseline) ───────────────

bench-vision:
	@mkdir -p benchmarks/vision
	python3 scripts/bench_vision.py \
		--models "$(MODEL)" \
		--images "$(IMAGES)" \
		--output-dir benchmarks/vision


clean:
	@find . -maxdepth 1 -type f \( -name 'compose_*.txt' -o -name '*_checks.json' -o -name 'verification_report.json' \) -print -delete

prune:
	@printf "Pruning Docker system...\n"
	docker system prune -f
	docker volume prune -f

up-open-websearch-mcp:
	$(COMPOSE_MAIN) up -d open-websearch-mcp

down-open-websearch-mcp:
	$(COMPOSE_MAIN) stop open-websearch-mcp

restart-open-websearch-mcp:
	$(COMPOSE_MAIN) restart open-websearch-mcp

logs-open-websearch-mcp:
	$(COMPOSE_MAIN) logs -f --tail=200 open-websearch-mcp

ps-open-websearch-mcp:
	$(COMPOSE_MAIN) ps open-websearch-mcp

test-open-websearch:
	@printf "Testing open-websearch-mcp connectivity...\n"
	@curl -s http://localhost:5050/mcp | grep -q "session ID" && echo "Connectivity OK (received session error as expected)" || (echo "Connectivity FAILED"; exit 1)

up-duckduckgo-mcp:
	$(COMPOSE_MAIN) up -d duckduckgo-mcp

down-duckduckgo-mcp:
	$(COMPOSE_MAIN) stop duckduckgo-mcp

restart-duckduckgo-mcp:
	$(COMPOSE_MAIN) restart duckduckgo-mcp

logs-duckduckgo-mcp:
	$(COMPOSE_MAIN) logs -f --tail=200 duckduckgo-mcp

ps-duckduckgo-mcp:
	$(COMPOSE_MAIN) ps duckduckgo-mcp
