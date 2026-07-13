
# vLLM stack
```sh
make build-vllm  #Build custom images
make download-vllm-models  # Pre-download ~44-60 GB of HF weights
make down-main && make up-vllm  # Swap Ollama → vLLM
```

## Smoke test: 
```sh
curl http://localhost:11434/v1/models
```