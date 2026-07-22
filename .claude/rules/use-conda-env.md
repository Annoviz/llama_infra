# Rule: Use llama_infra Conda Environment for Python Execution

All Python-related commands must be executed within the `llama_infra` conda environment to ensure dependency consistency and avoid polluting the system Python environment.

## Why

The project relies on specific versions of libraries (pinned in `workspace/requirements.txt`) that may conflict with system-wide packages or other environments. Running tools outside this environment leads to `ModuleNotFoundError` (e.g., missing `pytest`, `requests`) and inconsistent behavior between development and production.

## How to Apply

Prefix every Python command with `conda run -n llama_infra`.

### Examples

**Running a script:**
```bash
conda run -n llama_infra python3 tools/update_manager.py
```

**Running tests:**
```bash
conda run -n llama_infra python3 -m pytest -v tests/
```

**Installing dependencies (dev):**
```bash
conda run -n llama_infra pip install -r requirements-dev.txt
```

## Verification

If you suspect a command is running in the wrong environment, verify with:
```bash
conda run -n llama_infra python3 -c "import sys; print(sys.prefix)"
```
The output should point to the `llama_infra` conda directory, not `/usr/bin/python`.
