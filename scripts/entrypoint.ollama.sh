#!/bin/sh
set -eu

MODELS_CONFIG="${MODELS_CONFIG:-/app/workspace/models/models-config.yaml}"
MODELS_DIR="${OLLAMA_MODELS:-/models}"
MODE="serve"

if [ "${1:-}" = "--sync-only" ]; then
  MODE="sync"
elif [ "${1:-}" = "--validate-only" ]; then
  MODE="validate"
fi

log() {
  printf '%s\n' "$*"
}

trim_value() {
  value="$1"
  value="${value# }"
  value="${value% }"
  case "$value" in
    \"*\") value="${value#\"}"; value="${value%\"}" ;;
    \''*\') value="${value#\'}"; value="${value%\'}" ;;
  esac
  printf '%s' "$value"
}

download_if_missing() {
  target_path="$1"
  source_url="$2"

  if [ -f "$target_path" ]; then
    log "-I- Already exists: $target_path"
    return 0
  fi

  mkdir -p "$(dirname "$target_path")"
  if command -v curl >/dev/null 2>&1; then
    log "-I- Downloading with curl: $source_url -> $target_path"
    curl -fsSL "$source_url" -o "$target_path"
  elif command -v wget >/dev/null 2>&1; then
    log "-I- Downloading with wget: $source_url -> $target_path"
    wget -qO "$target_path" "$source_url"
  else
    log "-E- Cannot download $source_url because neither curl nor wget is available."
    return 1
  fi
}

sync_one_model() {
  model_id="$1"
  source_type="$2"
  ollama_model="$3"
  model_path="$4"
  model_url="$5"
  mmproj_path="$6"
  mmproj_url="$7"

  if [ -z "$model_id" ]; then
    log "-E- Each model entry must include 'id'."
    return 1
  fi

  if [ "$source_type" = "ollama" ]; then
    if [ -z "$ollama_model" ]; then
      log "-E- Model '$model_id' uses source_type=ollama but has no ollama_model."
      return 1
    fi
    if [ -n "$model_path$model_url$mmproj_path$mmproj_url" ]; then
      log "-E- Model '$model_id' mixes ollama and gguf fields; use one source type per model."
      return 1
    fi

    if [ "$MODE" = "validate" ]; then
      log "-I- Validated ollama model '$model_id' -> $ollama_model"
      return 0
    fi

    if [ "${MODELS_SYNC_DRY_RUN:-0}" = "1" ]; then
      log "-I- Dry-run: would pull ollama model '$ollama_model'"
      return 0
    fi

    log "-I- Pulling ollama model '$ollama_model'"
    ollama pull "$ollama_model"
    return 0
  fi

  if [ "$source_type" = "gguf" ]; then
    if [ -n "$ollama_model" ]; then
      log "-E- Model '$model_id' mixes gguf and ollama fields; use one source type per model."
      return 1
    fi
    if [ -z "$model_path" ]; then
      log "-E- Model '$model_id' uses source_type=gguf but has no model_path."
      return 1
    fi

    case "$model_path" in
      /models/*) ;;
      *) log "-E- Model '$model_id' has invalid model_path '$model_path'; expected /models/..."; return 1 ;;
    esac

    if [ "$MODE" = "validate" ]; then
      log "-I- Validated gguf model '$model_id' -> $model_path"
      return 0
    fi

    if [ -n "$model_url" ]; then
      download_if_missing "$model_path" "$model_url" || return 1
    elif [ ! -f "$model_path" ]; then
      log "-E- Model '$model_id' file not found and no model_url provided: $model_path"
      return 1
    fi

    if [ -n "$mmproj_url" ] && [ -z "$mmproj_path" ]; then
      log "-E- Model '$model_id' has mmproj_url but missing mmproj_path."
      return 1
    fi

    if [ -n "$mmproj_path" ]; then
      case "$mmproj_path" in
        /models/*) ;;
        *) log "-E- Model '$model_id' has invalid mmproj_path '$mmproj_path'; expected /models/..."; return 1 ;;
      esac

      if [ -n "$mmproj_url" ]; then
        download_if_missing "$mmproj_path" "$mmproj_url" || return 1
      elif [ ! -f "$mmproj_path" ]; then
        log "-E- Model '$model_id' mmproj file not found and no mmproj_url provided: $mmproj_path"
        return 1
      fi
    fi

    log "-I- GGUF model '$model_id' is ready."
    return 0
  fi

  log "-E- Model '$model_id' has unsupported source_type '$source_type'. Use ollama or gguf."
  return 1
}

run_sync() {
  if [ ! -f "$MODELS_CONFIG" ]; then
    log "-E- Models config not found: $MODELS_CONFIG"
    return 1
  fi

  log "-I- Sync mode: $MODE"
  log "-I- Models config: $MODELS_CONFIG"
  log "-I- Models directory: $MODELS_DIR"

  in_models=0
  seen_model=0

  model_id=""
  source_type=""
  ollama_model=""
  model_path=""
  model_url=""
  mmproj_path=""
  mmproj_url=""

  finalize_current() {
    if [ "$seen_model" -eq 1 ]; then
      sync_one_model "$model_id" "$source_type" "$ollama_model" "$model_path" "$model_url" "$mmproj_path" "$mmproj_url"
    fi
  }

  while IFS= read -r raw_line || [ -n "$raw_line" ]; do
    line="$(printf '%s' "$raw_line" | sed 's/[[:space:]]*$//')"
    case "$line" in
      ""|"#"*)
        continue
        ;;
      "models:")
        in_models=1
        continue
        ;;
      "  - id:"*)
        if [ "$in_models" -ne 1 ]; then
          continue
        fi
        finalize_current
        seen_model=1
        model_id="$(trim_value "${line#  - id:}")"
        source_type=""
        ollama_model=""
        model_path=""
        model_url=""
        mmproj_path=""
        mmproj_url=""
        ;;
      "    source_type:"*)
        source_type="$(trim_value "${line#    source_type:}")"
        ;;
      "    ollama_model:"*)
        ollama_model="$(trim_value "${line#    ollama_model:}")"
        ;;
      "    model_path:"*)
        model_path="$(trim_value "${line#    model_path:}")"
        ;;
      "    model_url:"*)
        model_url="$(trim_value "${line#    model_url:}")"
        ;;
      "    mmproj_path:"*)
        mmproj_path="$(trim_value "${line#    mmproj_path:}")"
        ;;
      "    mmproj_url:"*)
        mmproj_url="$(trim_value "${line#    mmproj_url:}")"
        ;;
      *)
        ;;
    esac
  done < "$MODELS_CONFIG"

  finalize_current
}

run_sync

if [ "$MODE" = "serve" ]; then
  exec ollama serve
fi

