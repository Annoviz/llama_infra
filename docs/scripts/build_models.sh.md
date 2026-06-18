# build_models.sh

## Purpose

Builds Ollama model aliases from Modelfile definitions. Registers custom models with Ollama using the `ollama create` command.

## Usage

```bash
scripts/build_models.sh
```

## Description

This script reads Modelfile definitions from `workspace/models/` and registers them as Ollama models:

- `Planner.Modelfile` → `planner` model
- `Coder.Modelfile` → `coder` model
- `FastCoder.Modelfile` → `fast-coder` model

## Examples

```bash
# Build all registered models
scripts/build_models.sh
```

## See Also

- [../services/ollama.md](../services/ollama.md) - Ollama service documentation
- [../../workspace/models/](../../workspace/models/) - Model definitions directory
