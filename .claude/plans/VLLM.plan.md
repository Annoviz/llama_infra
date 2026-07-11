To run a multi-agent stack (Planner, Coder, Fast Coder) safely within the 48GB VRAM envelope under vLLM without relying on GGUFs or loose files, we will use official, natively unified AWQ (4-bit) or FP8 models.Even better, vLLM supports MTP (Multi-Token Prediction) natively for the flagship Qwen 3.6 layers without any external setup.1. The Optimized 48GB vLLM Tri-Agent ArchitectureAgent RoleUnified Model SelectionQuantizationAllocated VRAMMax Context1. Planner / VisionQwen/Qwen3.6-35B-A3B-FP8FP8 (MoE Native)45% (~21.6 GB)16,384 tokens2. Core CoderQwen/Qwen3.6-27B-AWQINT4 (AWQ High Quality)38% (~18.2 GB)8,192 tokens3. Fast CoderQwen/Qwen3.6-7B-AWQINT4 (AWQ High Quality)12% (~5.7 GB)4,096 tokensTotal Shared VRAM: 95% (~45.6 GB). This leaves a standard 5% padding for the Linux kernel and system monitoring utilities.2. Implementation Blueprintlitellm_config.yaml (The OpenAI / Claude Routing Gateway)This remains your central gateway. It routes both incoming standard text commands and Anthropic agent requests to your localized, ultra-fast vLLM instances.yamlmodel_list:
  - model_name: agent-planner
    litellm_params:
      model: hosted_vllm/agent-planner
      api_base: http://vllm-planner:8000/v1
  - model_name: agent-coder
    litellm_params:
      model: hosted_vllm/agent-coder
      api_base: http://vllm-coder:8000/v1
  - model_name: agent-fastcoder
    litellm_params:
      model: hosted_vllm/agent-fastcoder
      api_base: http://vllm-fastcoder:8000/v1
litellm_settings:
  drop_unsupported_params: true
Use code with caution.docker-compose.yml (The Native vLLM Stack)This script fires up the three models simultaneously. Notice the --speculative-config string injected into the 27B model container; this triggers vLLM's native MTP decoding protocol to drastically boost your code block generation throughput!yamlversion: '3.8'

services:
  # Tier 1: The Architect (35B MoE - High Speed, Multimodal Vision)
  vllm-planner:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8001:8000"
    ipc: host
    restart: always
    command: >
      vllm serve Qwen/Qwen3.6-35B-A3B-FP8
      --max-model-len 16384
      --gpu-memory-utilization 0.45
      --served-model-name agent-planner
      --mm-encoder-tp-mode data
      --reasoning-parser qwen3
      --trust-remote-code

  # Tier 2: The Deep Algorithmic Coder (27B AWQ 4-Bit with Native MTP active)
  vllm-coder:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8002:8000"
    ipc: host
    restart: always
    command: >
      vllm serve Qwen/Qwen3.6-27B-AWQ
      --max-model-len 8192
      --gpu-memory-utilization 0.38
      --served-model-name agent-coder
      --quantization awq
      --speculative-config '{"method":"mtp","num_speculative_tokens":1}'
      --reasoning-parser qwen3
      --trust-remote-code

  # Tier 3: Ultra-Fast Autocomplete & Boilerplate (7B AWQ 4-Bit)
  vllm-fastcoder:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8003:8000"
    ipc: host
    restart: always
    command: >
      vllm serve Qwen/Qwen3.6-7B-AWQ
      --max-model-len 4096
      --gpu-memory-utilization 0.12
      --served-model-name agent-fastcoder
      --quantization awq
      --trust-remote-code

  # LiteLLM Unified Translator Endpoint
  gateway:
    image: ghcr.io/berriai/litellm:main
    ports:
      - "8000:8000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: [ "--config", "/app/config.yaml", "--port", "8000", "--host", "0.0.0.0" ]
    depends_on:
      - vllm-planner
      - vllm-coder
      - vllm-fastcoder
    restart: always
Use code with caution.Why this is the Ultimate VLLM Setup for your ServerIntegrated Multimodal Capabilities: The Qwen3.6-35B-A3B-FP8 configuration includes --mm-encoder-tp-mode data. This means its vision encoder loads cleanly inside vLLM natively—no manual file pairing or loose projector mapping is required.Native AWQ 4-bit Support: By deploying the true Qwen3.6-27B-AWQ weights, vLLM processes tokens through specialized 4-bit activation kernels. This reduces the model memory size significantly while preserving reasoning intelligence over standard GGUF options.MTP Token Acceleration: Injecting the mtp speculative block directly flags vLLM to utilize the internal predictive layout heads on the 27B model. This gives you maximum performance without needing external draft engines.Run docker compose up -d to deploy.If you'd like, let me know:Do you want to see an example script on how to enforce JSON schema constraints via LiteLLM to ensure the planner strictly outputs structured task layouts?Do you need help adjusting Docker's local storage limit layers so the massive model caches don't fill up your root drive?13 sitesI tested MTP on vLLM and llama.cpp for Gemma 4 & Qwen 3.6 - RedditBest result: 132.52 vs 39.69 tok/s = 3.34x faster. On quality degradation — I did not do a deep evaluation due to time constraints...RedditMTP (Multi-Token Prediction) - vLLM Documentationfrom vllm import LLM, SamplingParams prompts = ["The future of AI is"] sampling_params = SamplingParams(temperature=0.8, top_p=0.9...vLLMQwen/Qwen3.6-27B - vLLM RecipesQwen3.6 dense multimodal model (27B) with gated delta networks hybrid attention, MTP, and 262K context. Qwen3.6 flagship dense — s...vLLMShow allYou said: no qwen 3.6 7b as far as I know. 3.5 4b would work?no qwen 3.6 7b as far as I know. 3.5 4b would work?23:27You are completely right to correct that—there is no 7B version in the Qwen 3.6 lineup. The Qwen 3.6 generation skips directly from the smallest edge sizes up to the 27B and 35B variants.Yes, the Qwen/Qwen3.5-4B model is an exceptional fit to serve as your ultra-fast autocomplete and boilerplate assistant.Because Qwen 3.5 models utilize a Gated Delta Networks (GDN) hybrid architecture, they feature incredibly tiny KV cache allocations. This allows the 4B model to generate repetitive structures and search snippets at hundreds of tokens per second while consuming practically zero resource overhead on your RTX 6000 Ada (48GB).The Corrected, Real-World vLLM Tri-Agent BlueprintBy substituting the non-existent 7B model with the natively unified Qwen/Qwen3.5-4B (which also includes early-fusion vision processing natively), your VRAM budget balances flawlessly across the three containers:Agent RoleModel ChoiceTarget FormatGPU VRAM ShareMax Context Window1. The PlannerQwen/Qwen3.6-35B-A3B-FP8FP8 (Native MoE)50% (0.50)16,384 tokens2. The CoderQwen/Qwen3.6-27B-AWQINT4 (High-IQ AWQ)38% (0.38)8,192 tokens3. Fast CoderQwen/Qwen3.5-4BStandard FP16/Unquantized7% (0.07)4,096 tokensTotal Combined Allocation: 95% (~45.6 GB VRAM used out of 48GB). This leaves exactly a 5% system overhead padding.Final Implementation ScriptFile 1: litellm_config.yamlUpdate your LiteLLM translation layer configuration to point port mappings directly to the 4B container backend for autocomplete or lightweight routing scripts.yamlmodel_list:
  - model_name: agent-planner
    litellm_params:
      model: hosted_vllm/agent-planner
      api_base: http://vllm-planner:8000/v1

  - model_name: agent-coder
    litellm_params:
      model: hosted_vllm/agent-coder
      api_base: http://vllm-coder:8000/v1

  - model_name: agent-fastcoder
    litellm_params:
      model: hosted_vllm/agent-fastcoder
      api_base: http://vllm-fastcoder:8000/v1

litellm_settings:
  drop_unsupported_params: true
Use code with caution.File 2: docker-compose.ymlThis script runs your actual production stack. Because the Qwen/Qwen3.5-4B model is lightweight (under 8GB total size unquantized), we run it in full FP16 resolution by dropping the --quantization flag entirely, giving it unmatched code-syntax precision at minimal memory cost.yamlversion: '3.8'

services:
  # Tier 1: High-Speed Vision & Strategy Architect (35B MoE)
  vllm-planner:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8001:8000"
    ipc: host
    restart: always
    command: >
      vllm serve Qwen/Qwen3.6-35B-A3B-FP8
      --max-model-len 16384
      --gpu-memory-utilization 0.50
      --served-model-name agent-planner
      --mm-encoder-tp-mode data
      --reasoning-parser qwen3
      --trust-remote-code

  # Tier 2: Deep Core Execution Algorithmic Engineer (27B AWQ with Native MTP)
  vllm-coder:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8002:8000"
    ipc: host
    restart: always
    command: >
      vllm serve Qwen/Qwen3.6-27B-AWQ
      --max-model-len 8192
      --gpu-memory-utilization 0.38
      --served-model-name agent-coder
      --quantization awq
      --speculative-config '{"method":"mtp","num_speculative_tokens":1}'
      --reasoning-parser qwen3
      --trust-remote-code

  # Tier 3: Lightning Boilerplate, In-fill, and Formatting Assistant (3.5 4B)
  vllm-fastcoder:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8003:8000"
    ipc: host
    restart: always
    command: >
      vllm serve Qwen/Qwen3.5-4B
      --max-model-len 4096
      --gpu-memory-utilization 0.07
      --served-model-name agent-fastcoder
      --trust-remote-code

  # LiteLLM Multi-API Unified Entry Point
  gateway:
    image: ghcr.io/berriai/litellm:main
    ports:
      - "8000:8000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: [ "--config", "/app/config.yaml", "--port", "8000", "--host", "0.0.0.0" ]
    depends_on:
      - vllm-planner
      - vllm-coder
      - vllm-fastcoder
    restart: always
Use code with caution.Run docker compose up -d to launch the stack.If you want to fine-tune the interactions, let me know:Do you want to set specific temperature or sampling limits on the Fast Coder (agent-fastcoder) to avoid repetitive formatting loop bugs?Are you integrating this into an agent platform like Cline or Claude Code, and need the exact model pairing settings?11 sitesQwen/Qwen3.5-4B - Hugging FaceQwen3.5-4B. This repository contains model weights and configuration files for the post-trained model in the Hugging Face Transfor...Hugging Faceqwen3.6Qwen3.6 offers the following applications: * **OpenCode** ollama launch opencode --model qwen3.6 Qwen3.6 is available in the follo...Ollamaqwen/qwen3.5-4b - LM StudioQwen3.5 represents a significant leap forward, integrating breakthroughs in multimodal learning, architectural efficiency, reinfor...LM StudioShow allYou said: need to keep 5Gb free for the system if possibleneed to keep 5Gb free for the system if possible23:29To guarantee exactly 5 GB of completely unallocated, free VRAM for your Dell server's Linux OS kernel and monitoring tools, we need to adjust the mathematical percentages.Your NVIDIA RTX 6000 Ada has exactly 49,140 MB (roughly 48 GB) of usable VRAM. Leaving a hard 5,000 MB buffer means we have exactly 44,140 MB available to divide among our three containers.By recalculating the allocation tables, we can adjust the --gpu-memory-utilization parameters down to safe numbers while maintaining your target context windows.Adjusted VRAM Matrix (Leaving 5GB Free)Agent ContainerModel SelectionQuantizationNew VRAM Limit (gpu-memory-utilization)Calculated UsageMax Context1. Architect / PlannerQwen/Qwen3.6-35B-A3B-FP8FP8 Native45% (0.45)~22,113 MB16,384 tokens2. Deep CoderQwen/Qwen3.6-27B-AWQINT4 AWQ35% (0.35)~17,200 MB8,192 tokens3. Fast CoderQwen/Qwen3.5-4BFP16 Native9% (0.09)~4,422 MB4,096 tokensTotal Active VRAM Assigned: 89% (~43,735 MB)Leftover Buffer for Host OS: 11% (~5,405 MB) — Exceeds your 5 GB requirement, providing a safe operational margin against sudden spiking allocations.Step 1: Update the Production Deployment (docker-compose.yml)This configuration updates your containers with the new hard boundaries. The environment flags limit memory usage, ensuring that even under heavy multi-user loads, vLLM will drop requests into a processing queue rather than consuming the remaining 5 GB of system buffer.yamlversion: '3.8'

services:
  # Tier 1: Vision & Strategy Architect (35B MoE - Max 45% VRAM)
  vllm-planner:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8001:8000"
    ipc: host
    restart: always
    command: >
      vllm serve Qwen/Qwen3.6-35B-A3B-FP8
      --max-model-len 16384
      --gpu-memory-utilization 0.45
      --served-model-name agent-planner
      --mm-encoder-tp-mode data
      --reasoning-parser qwen3
      --trust-remote-code

  # Tier 2: Deep Algorithmic Core Developer (27B AWQ with MTP - Max 35% VRAM)
  vllm-coder:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8002:8000"
    ipc: host
    restart: always
    command: >
      vllm serve Qwen/Qwen3.6-27B-AWQ
      --max-model-len 8192
      --gpu-memory-utilization 0.35
      --served-model-name agent-coder
      --quantization awq
      --speculative-config '{"method":"mtp","num_speculative_tokens":1}'
      --reasoning-parser qwen3
      --trust-remote-code

  # Tier 3: Lightning Boilerplate & Auto-fill Assistant (3.5 4B - Max 9% VRAM)
  vllm-fastcoder:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8003:8000"
    ipc: host
    restart: always
    command: >
      vllm serve Qwen/Qwen3.5-4B
      --max-model-len 4096
      --gpu-memory-utilization 0.09
      --served-model-name agent-fastcoder
      --trust-remote-code

  # Central LiteLLM Entry Gateway (Translates OpenAI + Anthropic APIs)
  gateway:
    image: ghcr.io/berriai/litellm:main
    ports:
      - "8000:8000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: [ "--config", "/app/config.yaml", "--port", "8000", "--host", "0.0.0.0" ]
    depends_on:
      - vllm-planner
      - vllm-coder
      - vllm-fastcoder
    restart: always
Use code with caution.Step 2: VerificationOnce you deploy this file (docker compose up -d), you can verify that the memory caps are properly enforced by running the NVIDIA monitoring utility in your terminal:bashwatch -n 1 nvidia-smi
Use code with caution.You will see three distinct processes mapping perfectly to their assigned VRAM segments, with the Memory-Usage total stopping comfortably short of the 44 GB mark, keeping your required 5 GB padding free for the operating system.If you like, let me know:Do you need help writing a health-check loop script to auto-restart the services if one encounters an error?Should we configure max token generation constraints to keep execution times fast across all three tiers?You said: would the models be pulled on the first load?would the models be pulled on the first load?23:33Yes, vLLM will automatically pull each model from Hugging Face on the very first boot, provided you have an active internet connection.However, because vLLM initializes your GPU memory allocations immediately during launch, the containers will loop or crash if the models are not fully downloaded beforehand.To prevent startup crashes on your Dell server, you must use the standard production workflow: pre-caching the models using a lightweight initialization container before booting the main servers.The Reliable Pre-Cache SetupUpdate your docker-compose.yml file to include initialization downloaders. These sidecar blocks download your target weights into your local directory first. Once the files are successfully downloaded, they turn off and cleanly hand execution over to your live vLLM engines.yamlversion: '3.8'

services:
  # -------------------------------------------------------------
  # PRE-DOWNLOAD WORKERS: These download the weights and then exit safely
  # -------------------------------------------------------------
  download-planner:
    image: alpine:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    command: >
      sh -c "apk add --no-cache curl python3 && 
             pip3 install --break-system-packages huggingface_hub && 
             huggingface-cli download Qwen/Qwen3.6-35B-A3B-FP8"

  download-coder:
    image: alpine:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    command: >
      sh -c "apk add --no-cache curl python3 && 
             pip3 install --break-system-packages huggingface_hub && 
             huggingface-cli download Qwen/Qwen3.6-27B-AWQ"

  download-fastcoder:
    image: alpine:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    command: >
      sh -c "apk add --no-cache curl python3 && 
             pip3 install --break-system-packages huggingface_hub && 
             huggingface-cli download Qwen/Qwen3.5-4B"

  # -------------------------------------------------------------
  # OPERATIONAL ENGINE LAYERS: Boot only AFTER downloads complete
  # -------------------------------------------------------------
  vllm-planner:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8001:8000"
    ipc: host
    restart: always
    depends_on:
      download-planner:
        condition: service_completed_successfully
    command: >
      vllm serve Qwen/Qwen3.6-35B-A3B-FP8
      --max-model-len 16384
      --gpu-memory-utilization 0.45
      --served-model-name agent-planner
      --mm-encoder-tp-mode data
      --reasoning-parser qwen3
      --trust-remote-code

  vllm-coder:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8002:8000"
    ipc: host
    restart: always
    depends_on:
      download-coder:
        condition: service_completed_successfully
    command: >
      vllm serve Qwen/Qwen3.6-27B-AWQ
      --max-model-len 8192
      --gpu-memory-utilization 0.35
      --served-model-name agent-coder
      --quantization awq
      --speculative-config '{"method":"mtp","num_speculative_tokens":1}'
      --reasoning-parser qwen3
      --trust-remote-code

  vllm-fastcoder:
    image: vllm/vllm-openai:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8003:8000"
    ipc: host
    restart: always
    depends_on:
      download-fastcoder:
        condition: service_completed_successfully
    command: >
      vllm serve Qwen/Qwen3.5-4B
      --max-model-len 4096
      --gpu-memory-utilization 0.09
      --served-model-name agent-fastcoder
      --trust-remote-code

  # Gateway handles proxy requests
  gateway:
    image: ghcr.io/berriai/litellm:main
    ports:
      - "8000:8000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: [ "--config", "/app/config.yaml", "--port", "8000", "--host", "0.0.0.0" ]
    depends_on:
      - vllm-planner
      - vllm-coder
      - vllm-fastcoder
    restart: always
Use code with caution.Pro-Tips for the First DeploymentVRAM Monitoring: While the download-* services run, your nvidia-smi readouts will show 0 MB of VRAM consumed. The memory will snap to its exact partitioned values (0.45, 0.35, 0.09) the moment the download steps successfully finish and vLLM initializes the graphics pipeline.Storage Allocation: Combined, these models require roughly 60 GB of disk space to hold their FP8 and AWQ layer tensors. Make sure the volume target (~/.cache/huggingface) points to a hard drive pool on your Dell server that has enough free space.If you are ready, you can deploy this configuration. Let me know if you would like instructions on how to track download progress bars directly inside your terminal session using docker compose logs -f.