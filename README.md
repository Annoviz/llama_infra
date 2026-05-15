
# LLAMA INFRA - Llama.cpp, Ollama, AnythingLLM and more

* [ollama docker](https://hub.docker.com/r/ollama/ollama/tags)
* [ollama](https://github.com/ollama/ollama)
* [ollama-python](https://github.com/ollama/ollama-python)
* [Llama.cpp](https://github.com/ggml-org/llama.cpp)
* [Qwen2.5-VL-7b-Instruct-GGUF](https://huggingface.co/IAILabs/Qwen2.5-VL-7b-Instruct-GGUF/tree/main)
* [Llama.cpp-Local-OpenAI-server](https://github.com/Jaimboh/Llama.cpp-Local-OpenAI-server)
* [Llama.cpp-Local-OpenAI-server Medium](https://medium.com/@odhitom09/running-openais-server-locally-with-llama-cpp-5f29e0d955b7)
* [microsofts-phi-4](https://koshurai.medium.com/exploring-microsofts-phi-4-model-and-its-gguf-format-with-llama-cpp-aaccb816a5a8)

## Docker hub
* [ollama](https://hub.docker.com/r/ollama/ollama/tags)
* [anythingllm](https://hub.docker.com/r/mintplexlabs/anythingllm/tags)



## Usage - server
```
# ollama-server
docker compose up -d ollama-server

# anythingllm - https://github.com/Mintplex-Labs/anything-llm
docker compose up -d anythingllm

# ollama-server + anythingllm = localhost:3001
docker compose up -d anythingllm

# ollama-server + open-webui = localhost:3002
docker compose up -d open-webui

```


## Usage - client
```
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

## Usage - extra
```

# Run the lamma.cpp server - WIP
docker compose -f docker-compose.llama.cpp.yml up -d llamacpp-server

# Download the models - Qwen2.5-VL-7B-Instruct (Not supported by the server yet)
mkdir -p models/Qwen2.5-VL-7B-Instruct
cd models/Qwen2.5-VL-7B-Instruct
wget https://huggingface.co/IAILabs/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/README.md
wget https://huggingface.co/IAILabs/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/Qwen2.5-VL-7B-Instruct-Q4_0.gguf
wget https://huggingface.co/IAILabs/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/mmproj-Qwen2.5-VL-7B-Instruct-F32.gguf
cd ../..

# Build the python server
docker compose -f docker-compose.llama.cpp.yml build llamacpp-server-py

# Run the python server
docker compose -f docker-compose.llama.cpp.yml up -d llamacpp-server-py
```

## Update manager (Docker tags + Python packages)
```bash
# Check current vs latest (no file writes)
make updates-check

# Check and save proposal file (.update-manager-proposal.json)
make updates-suggest

# Show patch and apply only after interactive y/yes confirmation
make updates-apply
```

- Editable dependency source: `requirements-dev.txt`
- Frozen snapshot (never edited by update manager): `workspace/requirements.txt`

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

## Copilot subagents

This repo supports simple Markdown-based subagent discovery via `.github/agents/*.md`.

Available subagents:

- `docker-ops-agent` -> stack lifecycle, logs, GPU checks
- `model-config-agent` -> `workspace/configs/*.json`, `LLM_CONFIG`, GGUF/mmproj wiring
- `update-manager-agent` -> `tools/update_manager.py`, managed version/dependency updates
- `docs-sync-agent` -> `README.md` and `CHANGELOG.md` synchronization
- `coding-agent` -> implementation, refactors, bug fixes, and test updates
- `reviewer-agent` -> review findings, regressions, and missing-test analysis
- `commit-agent` -> stage, commit, and push workflows with status reporting

Routing modes:

- Manual routing: explicitly name a subagent in your prompt
- Proactive routing: infer subagent from task intent/keywords
- Strict proactive mode: use keyword scoring in `AGENTS.md` to pick the highest-confidence match

Validate subagent docs structure locally:

```bash
make check-agent-docs
make verify-agent-routing
```

Manual examples:

```text
Use update-manager-agent to run the update proposal flow.
Route this to model-config-agent and add a new config for a multimodal model.
```

Proactive examples:

```text
AnythingLLM is not starting, check logs and fix startup.
Add a new qwen config with model_alias and mmproj path.
Check for newer Docker tags and apply safe updates.
```

Fallback behavior:

- If intent is ambiguous, the orchestrator asks one short clarification question.
- If no confident match exists, the orchestrator handles the task directly.
- If work spans domains, the orchestrator can sequence multiple subagents.

# Contact
* Author: Dima Kanevsky
* [LinkedIn](https://www.linkedin.com/in/dmitry-dima-kanevsky-2a4a0438/)
* [github](https://github.com/dimakan)
* [Email](mailto:dima@annoviz.com)

# License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

# Citation
```bibtex
@misc{kanevsky2025llama,
  author = {Kanevsky, Dima},
  title = {Llama.cpp, Ollama, AnythingLLM and more},
  year = {2025},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/Annoviz/llama_infra}}
}
