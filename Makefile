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
COMPOSE_FALKOR := docker compose --project-directory $(CURDIR) \
	-f compose/main/00-networks-and-volumes.yml \
	-f compose/main/40-falkordb.yml \
	-f compose/main/50-falkordb-mcp.yml
COMPOSE_MAIN := docker compose --project-directory $(CURDIR) \
	-f compose/main/00-networks-and-volumes.yml \
	-f compose/main/10-ollama.yml \
	-f compose/main/20-anythingllm.yml \
	-f compose/main/30-open-webui.yml \
	-f compose/main/40-falkordb.yml \
	-f compose/main/50-falkordb-mcp.yml
COMPOSE_LLAMA := docker compose --project-directory $(CURDIR) -f docker-compose.llama.cpp.yml
LLAMA_CPP_IMAGE ?= ghcr.io/ggml-org/llama.cpp:full-cuda-b5350

.PHONY: help \
	config-main config-falkor config-llama config-all \
	pull-main pull-falkor pull-llama pull-all \
	build-llamacpp-py models-sync \
	updates-check updates-suggest updates-apply \
	check-agent-docs verify-agent-routing \
	precommit-install precommit-run precommit-update \
	up-ollama up-anythingllm up-open-webui up-main up-falkordb up-falkordb-mcp up-main-all \
	up-llamacpp up-llamacpp-py up-llama \
	down-main down-falkor down-llama down-all \
	restart-ollama restart-anythingllm restart-open-webui restart-falkordb restart-falkordb-mcp restart-llamacpp restart-llamacpp-py \
	logs-ollama logs-anythingllm logs-open-webui logs-falkordb logs-falkordb-mcp logs-llamacpp logs-llamacpp-py \
	ps-main ps-falkor ps-llama ps-all \
	gpu-host gpu-smoke-llamacpp clean

help:
	@printf "\nllama_infra utility targets\n\n"
	@printf "Main stack:\n"
	@printf "  make up-ollama           # Start Ollama only\n"
	@printf "  make up-anythingllm      # Start AnythingLLM (and Ollama dependency)\n"
	@printf "  make up-open-webui       # Start Open WebUI (and Ollama dependency)\n"
	@printf "  make up-main             # Start Ollama + AnythingLLM + Open WebUI\n"
	@printf "  make up-falkordb         # Start local FalkorDB service\n"
	@printf "  make up-falkordb-mcp     # Start FalkorDB MCP server (depends on FalkorDB)\n"
	@printf "  make up-main-all         # Start core stack + FalkorDB + FalkorDB MCP\n"
	@printf "  make down-main           # Stop the main stack\n"
	@printf "  make down-falkor         # Stop FalkorDB + MCP stack\n"
	@printf "\nllama.cpp stack:\n"
	@printf "  make up-llamacpp         # Start the native llama.cpp server\n"
	@printf "  make build-llamacpp-py   # Build the python llama-cpp server image\n"
	@printf "  make up-llamacpp-py      # Start the python llama-cpp server\n"
	@printf "  make down-llama          # Stop the llama.cpp stack\n"
	@printf "\nDiagnostics:\n"
	@printf "  make config-all          # Render both compose files\n"
	@printf "  make pull-all            # Pull all pinned images\n"
	@printf "  make models-sync         # Sync models from workspace/models/models-config.yaml inside ollama-server\n"
	@printf "  make ps-all              # Show running containers in both stacks\n"
	@printf "  make gpu-host            # Show host NVIDIA status\n"
	@printf "  make gpu-smoke-llamacpp  # Run a CUDA image smoke test with nvidia-smi\n"
	@printf "\nUpdate manager:\n"
	@printf "  make updates-check       # Check latest Docker tags and Python package versions\n"
	@printf "  make updates-suggest     # Check and write .update-manager-proposal.json\n"
	@printf "  make updates-apply       # Show diff and apply after interactive prompt\n"
	@printf "\nCode quality:\n"
	@printf "  make check-agent-docs    # Validate required headings in .github/agents/*.md\n"
	@printf "  make verify-agent-routing # Run agent docs checker + unit tests\n"
	@printf "  make precommit-install   # Install pre-commit git hooks\n"
	@printf "  make precommit-run       # Run all pre-commit hooks on all files\n"
	@printf "  make precommit-update    # Update pinned hook revisions in .pre-commit-config.yaml\n"
	@printf "\nOverride examples:\n"
	@printf "  OLLAMA_VERSION=0.18.2 make config-main\n"
	@printf "  IMAGE=ghcr.io/ggml-org/llama.cpp:full-cuda-b5343 make config-llama\n"
	@printf "  LLAMA_CPP_VERSION=0.3.18 REQUIREMENTS_FILE=requirements-dev.txt make build-llamacpp-py\n\n"
	@{ \
		printed=0; \
		if [ -n "$(DATA_DIR)" ]; then [ $$printed -eq 0 ] && printf "Detected environment:\n" && printed=1; printf "  DATA_DIR=%s\n" "$(DATA_DIR)"; fi; \
		if [ -n "$(REGISTRY)" ]; then [ $$printed -eq 0 ] && printf "Detected environment:\n" && printed=1; printf "  REGISTRY=%s\n" "$(REGISTRY)"; fi; \
		if [ -n "$(LLAMA_INFRA_DIR)" ]; then [ $$printed -eq 0 ] && printf "Detected environment:\n" && printed=1; printf "  LLAMA_INFRA_DIR=%s\n" "$(LLAMA_INFRA_DIR)"; fi; \
		[ $$printed -eq 1 ] && printf "\n" || true; \
	}

config-main:
	$(COMPOSE_CORE) config

config-falkor:
	$(COMPOSE_FALKOR) config

config-llama:
	$(COMPOSE_LLAMA) config

config-all: config-main config-falkor config-llama

pull-main:
	$(COMPOSE_CORE) pull

pull-falkor:
	$(COMPOSE_FALKOR) pull

pull-llama:
	$(COMPOSE_LLAMA) pull llamacpp-server

pull-all: pull-main pull-falkor pull-llama

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

precommit-install:
	pre-commit install

precommit-run:
	pre-commit run --all-files

precommit-update:
	pre-commit autoupdate

up-ollama:
	$(COMPOSE_CORE) up -d ollama-server

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

up-main-all:
	$(COMPOSE_MAIN) up -d ollama-server anythingllm open-webui falkordb falkordb-mcpserver

up-llamacpp:
	$(COMPOSE_LLAMA) up -d llamacpp-server

up-llamacpp-py:
	$(COMPOSE_LLAMA) up -d llamacpp-server-py

up-llama:
	$(COMPOSE_LLAMA) up -d llamacpp-server llamacpp-server-py

down-main:
	$(COMPOSE_CORE) down

down-falkor:
	$(COMPOSE_FALKOR) down

down-llama:
	$(COMPOSE_LLAMA) down

down-all: down-main down-falkor down-llama

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

logs-llamacpp:
	$(COMPOSE_LLAMA) logs -f --tail=200 llamacpp-server

logs-llamacpp-py:
	$(COMPOSE_LLAMA) logs -f --tail=200 llamacpp-server-py

ps-main:
	$(COMPOSE_CORE) ps

ps-falkor:
	$(COMPOSE_FALKOR) ps

ps-llama:
	$(COMPOSE_LLAMA) ps

ps-all: ps-main ps-falkor ps-llama

gpu-host:
	nvidia-smi

gpu-smoke-llamacpp:
	docker run --rm --gpus all --entrypoint nvidia-smi $(LLAMA_CPP_IMAGE)

clean:
	@find . -maxdepth 1 -type f \( -name 'compose_*.txt' -o -name '*_checks.json' -o -name 'verification_report.json' \) -print -delete
