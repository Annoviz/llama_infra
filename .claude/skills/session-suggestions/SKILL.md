---
name: session-suggestions
description: Analyze a conversation session and suggest Claude rules, workflow improvements or memory entries for llama_infra
---

# Skill: Session Suggestions

Analyze the current conversation session to suggest actionable improvements — Claude rules, workflow tweaks, or memory entries tailored to this infra project.

## Usage

```
/session-suggestions
/session-suggestions --accept-all
/session-suggestions --accept 1,3,5
```

**Note:** Run after a session has accumulated meaningful work (debugging, config changes, model swaps) for useful suggestions.

## What it does

1. Scans the current session transcript for recurring patterns and friction points
2. Generates suggestion categories:
   - **[rules]** — Behavioral rules to save in `.claude/rules/` (e.g., "always run `make verify-agent-routing` after AGENTS.md changes")
   - **[memory]** — Facts worth persisting (`~/.claude/projects/*/memory/`) so future sessions don't re-learn them
   - **[workflow]** — Makefile targets, script improvements, or compose tweaks born from session friction
3. Presents numbered suggestions for multi-selection
4. Creates rule files or memory entries when accepted

## Behavior

| Mode | Action |
|------|--------|
| Default (no args) | Show all suggestions with numbered options |
| `--accept-all` | Accept every suggestion automatically |
| `--accept 1,3` | Accept only the listed suggestions by number |

## Suggestion Categories for llama_infra

### Rules (`[rules]`)

Operational guardrails derived from session patterns:

- "Always rebuild model with `ollama create` after Modelfile edits"
- "Run `make gpu-host` before benchmarking to verify GPU availability"
- "Never edit `workspace/requirements.txt` directly — it's a frozen snapshot"
- "Use `conda run -n llama_infra` for test commands, not bare `python3`"

### Memory (`[memory]`)

Session learnings worth persisting:

- Model swap decisions (e.g., why Qwen3.5-4B over Qwen2.5-coder)
- GPU quirks discovered during debugging (VRAM limits, context caps)
- Ollama concurrency settings tuned for this hardware
- Known model issues (mmproj not loading, temperature sweet spots)

### Workflow (`[workflow]`)

Process improvements spotted during the session:

- Missing Makefile targets that would have saved time
- Compose file gaps (health checks, restart policies)
- Script enhancements (better error messages, missing flags)

## How It Works

The skill analyzes the current conversation by:

1. Reading recent tool calls and their outcomes from the session transcript
2. Detecting friction patterns (repeated failures, workarounds, manual steps that should be automated)
3. Checking what's already documented in `CLAUDE.md` / `.claude/rules/` to avoid duplicates
4. Generating concrete suggestions with file paths and example content

## Files

- `.claude/rules/` — Directory where rule files are created (one per suggestion)
- Each rule is saved as `<rule-slug>.md` with frontmatter: `name`, `description`, `trigger`
- Memory entries go to `~/.claude/projects/*/memory/` as per the memory system

## Example Flow

```
# After a session debugging Ollama model rebuilds...
/session-suggestions

# Output:
1. [rules] Always run 'ollama create' after Modelfile edits before testing
2. [memory] Qwen3.5-4B UD-Q4_K_XL needs mmproj-BF16.gguf for vision — document the rebuild step
3. [workflow] Add 'make model-rebuild NAME=fast-coder' target to Makefile

# Accept specific:
/session-suggestions --accept 1,2
```
