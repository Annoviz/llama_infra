
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



# Usage
```
# ollama-server
docker compose up -d ollama-server

# anythingllm - https://github.com/Mintplex-Labs/anything-llm
docker compose up -d anythingllm

# ollama-server + anythingllm = localhost:3001
docker compose up -d anythingllm

# ollama-server + open-webui = localhost:3002
docker compose up -d open-webui



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