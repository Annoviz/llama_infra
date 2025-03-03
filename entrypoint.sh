#!/usr/bin/env bash
export LLM_CONFIG=${LLM_CONFIG:-config.json}
export LLM_CONFIG_PATH=/app/workspace/configs/${LLM_CONFIG}
# Set the JUPYTER_LAB_CMD environment variable
JUPYTER_LAB_CMD=${JUPYTER_LAB_CMD:-jupyter-lab --no-browser --allow-root}
# Run the command with the given arguments
CMD="python3 -m llama_cpp.server --config_file $LLM_CONFIG_PATH"
echo "-I- Running the command: $CMD"
$JUPYTER_LAB_CMD &
$CMD

