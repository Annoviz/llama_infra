SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE_MAIN := docker compose -f docker-compose.yml
COMPOSE_LLAMA := docker compose -f docker-compose.llama.cpp.yml
LLAMA_CPP_IMAGE ?= ghcr.io/ggml-org/llama.cpp:full-cuda-b5350

.PHONY: help \
	config-main config-llama config-all \
	pull-main pull-llama pull-all \
	build-llamacpp-py \
	updates-check updates-suggest updates-apply \
	precommit-install precommit-run precommit-update \
	up-ollama up-anythingllm up-open-webui up-main \
	up-llamacpp up-llamacpp-py up-llama \
	down-main down-llama down-all \
	restart-ollama restart-anythingllm restart-open-webui restart-llamacpp restart-llamacpp-py \
	logs-ollama logs-anythingllm logs-open-webui logs-llamacpp logs-llamacpp-py \
	ps-main ps-llama ps-all \
	gpu-host gpu-smoke-llamacpp clean

help:
	@printf "\nllama_infra utility targets\n\n"
	@printf "Main stack:\n"
	@printf "  make up-ollama           # Start Ollama only\n"
	@printf "  make up-anythingllm      # Start AnythingLLM (and Ollama dependency)\n"
	@printf "  make up-open-webui       # Start Open WebUI (and Ollama dependency)\n"
	@printf "  make up-main             # Start Ollama + AnythingLLM + Open WebUI\n"
	@printf "  make down-main           # Stop the main stack\n"
	@printf "\nllama.cpp stack:\n"
	@printf "  make up-llamacpp         # Start the native llama.cpp server\n"
	@printf "  make build-llamacpp-py   # Build the python llama-cpp server image\n"
	@printf "  make up-llamacpp-py      # Start the python llama-cpp server\n"
	@printf "  make down-llama          # Stop the llama.cpp stack\n"
	@printf "\nDiagnostics:\n"
	@printf "  make config-all          # Render both compose files\n"
	@printf "  make pull-all            # Pull all pinned images\n"
	@printf "  make ps-all              # Show running containers in both stacks\n"
	@printf "  make gpu-host            # Show host NVIDIA status\n"
	@printf "  make gpu-smoke-llamacpp  # Run a CUDA image smoke test with nvidia-smi\n"
	@printf "\nUpdate manager:\n"
	@printf "  make updates-check       # Check latest Docker tags and Python package versions\n"
	@printf "  make updates-suggest     # Check and write .update-manager-proposal.json\n"
	@printf "  make updates-apply       # Show diff and apply after interactive prompt\n"
	@printf "\nCode quality:\n"
	@printf "  make precommit-install   # Install pre-commit git hooks\n"
	@printf "  make precommit-run       # Run all pre-commit hooks on all files\n"
	@printf "  make precommit-update    # Update pinned hook revisions in .pre-commit-config.yaml\n"
	@printf "\nOverride examples:\n"
	@printf "  OLLAMA_VERSION=0.18.2 make config-main\n"
	@printf "  IMAGE=ghcr.io/ggml-org/llama.cpp:full-cuda-b5343 make config-llama\n"
	@printf "  LLAMA_CPP_VERSION=0.3.18 REQUIREMENTS_FILE=requirements-dev.txt make build-llamacpp-py\n\n"

config-main:
	$(COMPOSE_MAIN) config

config-llama:
	$(COMPOSE_LLAMA) config

config-all: config-main config-llama

pull-main:
	$(COMPOSE_MAIN) pull

pull-llama:
	$(COMPOSE_LLAMA) pull llamacpp-server

pull-all: pull-main pull-llama

build-llamacpp-py:
	$(COMPOSE_LLAMA) build llamacpp-server-py

updates-check:
	python3 tools/update_manager.py check

updates-suggest:
	python3 tools/update_manager.py suggest

updates-apply:
	python3 tools/update_manager.py apply

precommit-install:
	pre-commit install

precommit-run:
	pre-commit run --all-files

precommit-update:
	pre-commit autoupdate

up-ollama:
	$(COMPOSE_MAIN) up -d ollama-server

up-anythingllm:
	$(COMPOSE_MAIN) up -d anythingllm

up-open-webui:
	$(COMPOSE_MAIN) up -d open-webui

up-main:
	$(COMPOSE_MAIN) up -d ollama-server anythingllm open-webui

up-llamacpp:
	$(COMPOSE_LLAMA) up -d llamacpp-server

up-llamacpp-py:
	$(COMPOSE_LLAMA) up -d llamacpp-server-py

up-llama:
	$(COMPOSE_LLAMA) up -d llamacpp-server llamacpp-server-py

down-main:
	$(COMPOSE_MAIN) down

down-llama:
	$(COMPOSE_LLAMA) down

down-all: down-main down-llama

restart-ollama:
	$(COMPOSE_MAIN) restart ollama-server

restart-anythingllm:
	$(COMPOSE_MAIN) restart anythingllm

restart-open-webui:
	$(COMPOSE_MAIN) restart open-webui

restart-llamacpp:
	$(COMPOSE_LLAMA) restart llamacpp-server

restart-llamacpp-py:
	$(COMPOSE_LLAMA) restart llamacpp-server-py

logs-ollama:
	$(COMPOSE_MAIN) logs -f --tail=200 ollama-server

logs-anythingllm:
	$(COMPOSE_MAIN) logs -f --tail=200 anythingllm

logs-open-webui:
	$(COMPOSE_MAIN) logs -f --tail=200 open-webui

logs-llamacpp:
	$(COMPOSE_LLAMA) logs -f --tail=200 llamacpp-server

logs-llamacpp-py:
	$(COMPOSE_LLAMA) logs -f --tail=200 llamacpp-server-py

ps-main:
	$(COMPOSE_MAIN) ps

ps-llama:
	$(COMPOSE_LLAMA) ps

ps-all: ps-main ps-llama

gpu-host:
	nvidia-smi

gpu-smoke-llamacpp:
	docker run --rm --gpus all --entrypoint nvidia-smi $(LLAMA_CPP_IMAGE)

clean:
	@find . -maxdepth 1 -type f \( -name 'compose_*.txt' -o -name '*_checks.json' -o -name 'verification_report.json' \) -print -delete
