
------------------------------
## 🗺️ Comprehensive Execution Plan: Local Claude Code & Ollama
This standalone markdown playbook outlines the end-to-end setup, infrastructure configurations, custom model specifications, and execution validation scripts to build a private engineering workspace on an NVIDIA RTX 6000 Ada (48GB VRAM).
------------------------------
## 📋 Phase 1: Docker Infrastructure Setup

* Action: Open or create your docker-compose.yml file.
* Action: Configure the environment and hardware pass-through exactly as defined below.

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - OLLAMA_KEEP_ALIVE=24h        # Retains models in VRAM for instant CLI responses
      - OLLAMA_NUM_PARALLEL=4        # Handles concurrent tool calls and lookups smoothly
      - OLLAMA_MAX_LOADED_MODELS=2   # Permits Planner and Coder to reside in VRAM simultaneously
      - OLLAMA_FLASH_ATTENTION=1     # Dramatically accelerates execution on Ada architecture
volumes:
  ollama_data:


* Action: Spin up the container stack: docker compose up -d --force-recreate.
* Action: Verify hardware attachment: docker exec -it ollama nvidia-smi. Ensure the 48GB VRAM pool is detected.

------------------------------
## 🛠️ Phase 2: Model Artifact Engineering

* Action: Create a tracking directory: mkdir -p ~/claude-local-workspace && cd ~/claude-local-workspace.
* Action: Write out the discrete blueprint files for both layers of your reasoning workflow.

## 📄 File Planner.Modelfile

# Base Architecture: Multi-modal thinking model with 1M native contextFROM qwen3.6:35b
# Target Configuration for 48GB VRAM Pool
PARAMETER num_gpu 99            # Mandate 100% GPU layer offloading
PARAMETER num_ctx 65536         # Allocate 64k tokens for project-wide structural awareness
PARAMETER temperature 0.1       # Enforce highly strict, deterministic structural execution
PARAMETER keep_alive 24h        # Prevent VRAM cache purges between planning phases

SYSTEM """
You are the heavy Planning Agent (Opus-Tier). Your role is purely analytical.
Analyze structural dependencies, plan multi-file refactors, and diagnose systemic bugs.
Output rigorous system architectures and steps for the implementation agent to fulfill.
"""

## 📄 File Coder.Modelfile

# Base Architecture: Highly optimized flagship code generation engineFROM qwen2.5-coder:14b
# Target Configuration for Low-latency High-throughput Generation
PARAMETER num_gpu 99            # Mandate 100% GPU layer offloading
PARAMETER num_ctx 32768         # Allocate 32k tokens context window for operational file editing
PARAMETER temperature 0.3       # Allow slight stylistic variance while maintaining correctness
PARAMETER keep_alive 24h        # Keep resident alongside the planner model in memory

SYSTEM """
You are the execution Coder Agent (Sonnet-Tier). Your job is rapid, precise implementation.
Read structural manifests or directions given by the Planner, then write perfect, clean code.
Adhere strictly to instructions and execute file operations natively.
"""


* Action: Create the build automation engine: nano build_models.sh. Paste the following shell snippet:

#!/bin/bash
echo "🧱 Constructing Custom Local Inference Engines..."
docker exec -i ollama ollama create planner -f - < Planner.Modelfile
docker exec -i ollama ollama create coder -f - < Coder.Modelfile
echo "✅ Compilation Complete. Run 'docker exec -it ollama ollama list' to inspect."


* Action: Execute compilation: chmod +x build_models.sh && ./build_models.sh.

------------------------------
## ⚙️ Phase 3: Host Environment & Shell Tool Routing

* Action: Open your environment configurations: nano ~/.zshrc (or ~/.bashrc).
* Action: Append the isolated network routing aliases to map directly to your local Docker instance:

# Isolated Local Agent Routing (0% Account Tracing)
alias planner='export ANTHROPIC_BASE_URL=http://localhost:11434/v1 && export ANTHROPIC_AUTH_TOKEN=ollama && claude --model ollama/planner'
alias coder='export ANTHROPIC_BASE_URL=http://localhost:11434/v1 && export ANTHROPIC_AUTH_TOKEN=ollama && claude --model ollama/coder'
# Standard Team / Corporate Cloud Routing
alias claude-work='unset ANTHROPIC_BASE_URL && unset ANTHROPIC_AUTH_TOKEN && CLAUDE_CONFIG_DIR=~/.claude-work claude'


* Action: Source changes immediately: source ~/.zshrc (or source ~/.bashrc).

------------------------------
## 🧪 Phase 4: Active Validation, Telemetry & Performance Monitoring

* Action: Open a dedicated window split to track hardware utilization: watch -n 0.5 nvidia-smi.
* Action: Initialize a project space and launch the heavy model: cd /your/target/codebase && planner.
* Action: Submit an initial architectural query to watch the memory cache form.
* Action: Use the terminal-level command interface inside Claude Code to swap back and forth natively:
* Swap to rapid coding execution: /model ollama/coder.
   * Swap to complex architectural planning: /model ollama/planner.

------------------------------
## 📊 Phase 5: Automated Telemetry & Benchmarking Engine

* Action: Create a script named benchmark.py inside your workspace directory. This will track execution speed (tokens per second) across your hardware layers to ensure optimum setup performance.

import timeimport requestsimport json
def eval_speed(model_endpoint):
    payload = {
        "model": model_endpoint,
        "prompt": "Write an optimized async connection pool worker script in Python.",
        "stream": False,
        "options": {"num_ctx": 4096}
    }
    print(f"⚡ Testing generation efficiency on model target: '{model_endpoint}'...")
    start = time.time()
    res = requests.post("http://localhost:11434/api/generate", json=payload)
    end = time.time()
    
    if res.status_code == 200:
        data = res.json()
        tokens = data.get("eval_count", 0)
        duration_ns = data.get("eval_duration", 1)
        duration_sec = duration_ns / 1_000_000_000
        tps = tokens / duration_sec if duration_sec > 0 else 0
        print(f"📊 Speed Metrics: {tps:.2f} Tokens/Sec (Generated {tokens} tokens in {duration_sec:.2f}s)\n")
    else:
        print(f"❌ Connection error on target model: {res.text}")
if __name__ == "__main__":
    eval_speed("planner")
    eval_speed("coder")

------------------------------
If your automated benchmarks or real-world project trees encounter memory constraints, would you like me to guide you through adjusting the Mirostat parameters or utilizing GGUF layer splitting strategies to balance the architecture?

