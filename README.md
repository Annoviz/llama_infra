
# LLAMA INFRA - Llama.cpp, Ollama, AnythingLLM and more

* [ollama docker](https://hub.docker.com/r/ollama/ollama/tags)
* [ollama](https://github.com/ollama/ollama)
* [ollama-python](https://github.com/ollama/ollama-python)
* [Llama.cpp](https://github.com/ggml-org/llama.cpp)
* [Qwen2.5-VL-7b-Instruct-GGUF](https://huggingface.co/IAILabs/Qwen2.5-VL-7b-Instruct-GGUF/tree/main)
* [Llama.cpp-Local-OpenAI-server](https://github.com/Jaimboh/Llama.cpp-Local-OpenAI-server)
* [Llama.cpp-Local-OpenAI-server Medium](https://medium.com/@odhitom09/running-openais-server-locally-with-llama-cpp-5f29e0d955b7)
* [microsofts-phi-4](https://koshurai.medium.com/exploring-microsofts-phi-4-model-and-its-gguf-format-with-llama-cpp-aaccb816a5a8)



# Usage
```
# ollama-server
docker compose up -d ollama-server

# anythingllm - https://github.com/Mintplex-Labs/anything-llm
docker compose up -d anythingllm

# ollama-server + anythingllm
docker compose up -d ollama-server anythingllm



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
