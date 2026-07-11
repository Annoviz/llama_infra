---
name: review-and-commit
description: Review git diff for issues, verify changes align with project conventions, then commit and optionally push
---

# Skill: Review and Commit

Review all uncommitted changes in `git diff HEAD`, check them against project conventions, fix any issues found, then commit (and optionally push).

## Usage

```
/review-and-commit                # Auto-generate commit message, no push
/review-and-commit <message>      # Use custom commit message, no push
/review-and-commit --push         # Commit and push (auto-generated message)
/review-and-commit "<msg>" --push # Commit with custom message and push
```

## Workflow

### 1. Review the full diff

```bash
git status
git diff HEAD
```

Read every changed file's hunk carefully. Do NOT rely on `--stat` alone — it hides what actually changed.

### 2. Check against llama_infra conventions

Apply these project-specific checks:

#### Modelfiles (`workspace/models/*.Modelfile`)
- **Base model sanity**: Verify the `FROM` line points to an existing blob (not a typo'd path)
- **mmproj pairing**: If vision is intended, both base GGUF and mmproj lines must be present and uncommented
- **Parameter consistency**: Check that `num_gpu`, `temperature`, `num_ctx` match intent

#### Compose files (`compose/main/*.yml`)
- **Version alignment**: Docker image tags should match `.env` variables (e.g., `OLLAMA_VERSION`)
- **Env var layering**: No hardcoded secrets; values should come from `.env` or service-level env blocks
- **Port collisions**: Verify no two services expose the same host port

#### Makefile
- **PHONY declaration**: New targets must be listed in `.PHONY`
- **Help text**: New user-facing targets should appear under `help:` output

#### Scripts (`scripts/*.py`, `tools/*.py`)
- **Shebang + permissions**: Python scripts should have `#!/usr/bin/env python3`
- **Error handling**: Exit codes set via `sys.exit(1)` on failures, not bare exceptions

#### Config files (`workspace/models/*.json`, `models-config.yaml`)
- **Path consistency**: Model paths use `/models/...` mount convention
- **Schema compliance**: Required fields present (`model_alias`, `chat_format`, etc.)

#### Docs (`README.md`, `CHANGELOG.md`)
- **Sync check**: If behavior changed, docs should reflect it
- **Link validity**: No broken relative links

### 3. Run validation commands if applicable

```bash
# If AGENTS.md or agent files changed:
make verify-agent-routing

# If compose files changed:
make config-all

# If Python scripts changed:
conda run -n llama_infra python3 -m pytest -q tests/

# If markdown links were added:
make check-doc-links
```

### 4. Fix any issues found

Apply fixes before committing:

- **Prefer `sed` for simple replacements** — the Edit tool can fail on stale file state:
  ```bash
  sed -i 's/old-text/new-text/g' path/to/file.md
  ```
- **Use Edit for multi-line structural changes** (adding sections, reformatting blocks)

### 5. Verify fixes and re-read before committing

After fixing:
```bash
git diff HEAD --stat    # Confirm only intended changes remain
git diff HEAD           # Spot-check key hunks
```

**Important:** If you need to read a file after making edits, use `cat <file>` via Bash instead of the Read tool — it always reads from disk.

### 6. Commit with descriptive message

Generate a conventional commit message:

| Change type | Prefix | Example |
|-------------|--------|---------|
| Modelfile swap | `model:` | `model: switch fast-coder to Qwen3.5-4B UD-Q4_K_XL` |
| Docker/compose change | `infra:` | `infra: add FalkorDB MCP health check` |
| Script/tool update | `chore:` | `chore: bump ollama 0.31.1, falkordb mcp 1.3.0` |
| Doc update | `docs:` | `docs: sync README with new make targets` |
| Test addition | `test:` | `test: add vision_test.py multimodal smoke test` |
| Bug fix | `fix:` | `fix: correct port mapping for open-webui` |

```bash
git add <changed-files>
git commit -m "<type>: <short summary>" -m "<detail if needed>" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 7. Push (only with --push flag)

```bash
git push origin HEAD
```

Report branch, commit hash, and push result.

## Common Issues to Watch For

| Issue | Context | Fix |
|-------|---------|-----|
| Modelfile edited but model not rebuilt | Vision won't work until `ollama create` runs | Remind user or run rebuild via compose |
| Hardcoded values in compose files | Should use `.env` variables | Replace with `${VAR}` references |
| Missing PHONY for new Makefile target | Target only fires once, then thinks file exists | Add to `.PHONY` block |
| Docs out of sync after feature change | README/CHANGELOG not updated | Update docs before committing |
| `workspace/requirements.txt` modified | Frozen snapshot — never edit directly | Flag as error; suggest re-freezing workflow |

## Example

**User:** `/review-and-commit --push`

**You do:**
1. `git status` + `git diff HEAD` — see Modelfile changes and new script
2. Notice `vision_test.py` missing from help text → add Makefile entry
3. Run `make config-all` → compose is fine
4. `git diff HEAD --stat` — verify only intended changes remain
5. Commit: `model: switch fast-coder to Qwen3.5-4B UD-Q4_K_XL; add vision-test skill and script`
6. Push to origin/main
