# Operations guide

This document contains day-to-day operational workflows that were moved out of the top-level README.

## Client setup

```bash
# install mini conda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod +x Miniconda3-latest-Linux-x86_64.sh
./Miniconda3-latest-Linux-x86_64.sh

# create a new conda environment
conda create -n llama_infra python=3.10

# activate the conda environment
conda activate llama_infra

# install the client requirements
pip install -r requirements-client.txt

# run the client examples with jupyter: workspace/ollama_examples.ipynb
jupyter notebook
```

## Extra workflows

```bash
# Run the lamma.cpp server - WIP
make up-llamacpp

# Sync models inside the ollama-server container
make models-sync

# Download the models - Qwen2.5-VL-7B-Instruct (Not supported by the server yet)
mkdir -p models/Qwen2.5-VL-7B-Instruct
cd models/Qwen2.5-VL-7B-Instruct
wget https://huggingface.co/IAILabs/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/README.md
wget https://huggingface.co/IAILabs/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/Qwen2.5-VL-7B-Instruct-Q4_0.gguf
wget https://huggingface.co/IAILabs/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/mmproj-Qwen2.5-VL-7B-Instruct-F32.gguf
cd ../..

# Build the python server
make build-llamacpp-py

# Run the python server
make up-llamacpp-py
```

## Local Claude Code playbook

- Repo-aligned setup guide: CLAUDE_CODE_LOCAL.md
- Uses Makefile-first commands for Ollama lifecycle (make up-ollama, make logs-ollama, make ps-main)
- Covers model alias creation (planner, coder), shell routing aliases, and local benchmarking

## Model config locations

- Llama.cpp JSON server configs: workspace/models/*.json
- Model sync contract: workspace/models/models-config.yaml
- LLM_CONFIG is resolved as /app/workspace/models/${LLM_CONFIG} in scripts/entrypoint.llamacpp.sh
- Ollama startup and sync entrypoint: scripts/entrypoint.ollama.sh

## Update manager

- Update workflow reference: tools/README.md
- Version pinning and upgrade checklist: docs/versioning.md
- Editable dependency source: requirements-dev.txt
- Frozen snapshot (report-only): workspace/requirements.txt

## Code quality (pre-commit)

```bash
# install dev tooling
pip install -r requirements-dev.txt

# install git pre-commit hook
make precommit-install

# run all hooks manually
make precommit-run

# run focused agent routing verification
make verify-agent-routing

# refresh pinned hook revisions
make precommit-update
```
