# Scripts Documentation

This directory contains documentation for all scripts in the `scripts/` and `tools/` directories.

## Shell Scripts

| Script | Purpose |
|--------|---------|
| [aliases.sh](aliases.sh.md) | Shell aliases for Claude Cloud/Local configuration |
| [bench.sh](bench.sh.md) | Model benchmark runner with regression comparison |
| [build_models.sh](build_models.sh.md) | Build Ollama model aliases from Modelfiles |
| [claude-local-picker.sh](claude-local-picker.sh.md) | Interactive Ollama model picker for Claude |
| [entrypoint.llamacpp.sh](entrypoint.llamacpp.sh.md) | Entrypoint for llama.cpp Python server |
| [entrypoint.ollama.sh](entrypoint.ollama.sh.md) | Entrypoint for Ollama with model sync |
| [perf_test.sh](perf_test.sh.md) | Performance test runner (calls perf_test.py) |

## Python Scripts

| Script | Purpose |
|--------|---------|
| [model_regression.py](model_regression.py.md) | Compare benchmark runs against reference results |
| [check_agent_docs.py](check_agent_docs.py.md) | Validate subagent markdown docs structure |
| [check_doc_links.py](check_doc_links.py.md) | Verify local markdown links resolve |
| [update_manager.py](update_manager.py.md) | Docker tag and Python package version management |

## Related Documentation

- [../operations.md](../operations.md) - Day-to-day workflows including benchmarking
- [../versioning.md](../versioning.md) - Version pinning and update workflow
