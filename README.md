
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



## Service docs

Main stack:

- Ollama: [docs/services/ollama.md](docs/services/ollama.md)
- AnythingLLM: [docs/services/anythingllm.md](docs/services/anythingllm.md)
- Open WebUI: [docs/services/open-webui.md](docs/services/open-webui.md)
- FalkorDB: [docs/services/falkordb.md](docs/services/falkordb.md)
- FalkorDB MCP: [docs/services/falkordb-mcp.md](docs/services/falkordb-mcp.md)
- Unsloth: [docs/services/unsloth.md](docs/services/unsloth.md)

llama.cpp stack:

- llama.cpp services: [docs/services/llama-cpp.md](docs/services/llama-cpp.md)

General stack orchestration:

- Top-level commands and shortcuts: [Makefile](Makefile) (`make help`)
- Version pinning and update workflow: [docs/versioning.md](docs/versioning.md)
- Operations guide (client setup, extra workflows, model config, update manager, code quality): [docs/operations.md](docs/operations.md)
- Subagents and routing rules: [AGENTS.md](AGENTS.md)

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
