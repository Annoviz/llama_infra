# you asked

can llama-server by itself run multiple models dynamicly?

---

# googlesearch response

**Yes, `llama-server` can now run and route multiple models dynamically by itself using its native Router Mode.**

You no longer need external proxies like LiteLLM or third-party wrappers to achieve this. Recent updates to `llama.cpp` introduced **native request routing, auto-discovery, and dynamic LRU (Least Recently Used) VRAM eviction** directly into the binary.

The system spawns separate worker processes for each active model behind a unified OpenAI-compatible endpoint.

* * *

Method 1: The Quick Directory Approach

If you have a folder full of standard text GGUFs, you can point `llama-server` directly to it. It will auto-detect the models and spin up the router.

```bash
llama-server --models-dir /path/to/your/gguf/folder --models-max 3
```

Use code with caution.

-   **How it works:** When a client sends an OpenAI-compatible completion request with a specific `"model": "filename.gguf"`, `llama-server` dynamically loads that file into memory on demand.
-   **`--models-max 3`**: Tells the server to only keep a maximum of 3 models in VRAM at once. If you call a 4th, it unloads the oldest one automatically.

* * *

Method 2: The Complex `mmproj` (Vision) Configuration

Because you are using **multimodal models with discrete `mmproj` architecture links**, the simple directory scanner above isn't enough. You must explicitly tie each unique text GGUF to its corresponding vision projector.

To do this natively in `llama-server`, you use a **Preset File**.

1\. Create a Configuration File (`models.ini`)

Define global default settings under `[*]`, and then map out your specific models individually along with their required `--mmproj` tags.

```ini
[*]
# Global default hardware settings applied to all models
ngl = 99
ctx-size = 4096

[qwen-35b-vision]
model = ./Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL.gguf
mmproj = ./mmproj-BF16.gguf
# Overrides for the flagships MTP speculation layers
spec-type = draft-mtp
spec-draft-n-max = 2

[qwen-8b-vision]
model = ./Qwen3-vl-8b.gguf
mmproj = ./mmproj-Qwen3-8b-f16.gguf
```

Use code with caution.

2\. Launch the Router Native Mode

Pass this preset config file into the command execution string without passing a single model flag:

```bash
llama-server --models-preset ./models.ini --port 8080
```

Use code with caution.

3\. Query the Engine

Your single endpoint on port `8080` will now seamlessly accept standard API calls targeting either model payload layout:

```bash
# Targets the 35B vision stack
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{ "model": "qwen-35b-vision", "messages": [...] }'

# Targets the 8B vision stack
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{ "model": "qwen-8b-vision", "messages": [...] }'
```

Use code with caution.

* * *

The Fine Print: Memory & Context Caps

While this eliminates the need for an external tool like LiteLLM, you are still bound by hardware mechanics:

-   **Parallel Execution VRAM:** If you want both models to serve parallel requests at 0ms latency, your combined VRAM must accommodate the _sum_ of both models plus their context windows.
-   **Dynamic Swapping Delays:** If your VRAM is limited and `llama-server` has to constantly drop the 35B model to disk to read the 8B model into the GPU, you will still experience a 5-15 second loading hitch during the handoff.

If you want to fine-tune this native setup, tell me:

-   What **GPU(s)** and how much total **VRAM** are you working with?
-   Do you want help configuring **VRAM offloading constraints** inside the `.ini` file so they both fit at once?

Share

More