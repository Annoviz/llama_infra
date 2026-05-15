# AGENTS.md - Router and Global Rules for llama_infra

This file is the top-level orchestrator for agent behavior in this repo.

Detailed, task-specific guidance is delegated to Markdown subagents in
`.github/agents/`.

## Architecture Snapshot

Two independent Docker stacks are supported:

1. Main stack (`docker-compose.yml`): Ollama + AnythingLLM + Open WebUI
2. llama.cpp stack (`docker-compose.llama.cpp.yml`): native C++ server + Python server

These stacks are intentionally separate; do not assume cross-stack compatibility.

## Global Rules (Always Apply)

1. Use `make` commands instead of raw `docker compose` commands when a matching Make target exists.
2. Keep settings config-first: model/server values belong in JSON configs and env vars, not hardcoded values.
3. Preserve environment layering: `.env` -> compose env -> container env.
4. Treat `workspace/requirements.txt` as frozen (report-only in automation).
5. Keep data safety expectations explicit (for example, never suggest deleting `./models`).
6. After implementation, include a brief PR-style note with: what changed, validation run, and recommended next steps.
7. Keep docs in sync: update `README.md` and/or `CHANGELOG.md` when behavior or workflow changes.
8. End each agent session with 1-3 actionable improvements to the agent workflow.

## Subagent Discovery Convention (Simple Markdown)

- Location: `.github/agents/*.md`
- Each subagent file should include these headings:
  - `# <Agent Name>`
  - `## Purpose`
  - `## Owns`
  - `## Triggers`
  - `## Workflow`
  - `## Boundaries`
  - `## Handoff Back`
  - `## Example Prompt`

## Routing Modes

### 1) Manual (explicit)

If the user explicitly requests a subagent by name, route directly to that subagent.

Examples:
- "Use `update-manager-agent` for this"
- "Route this to the model config subagent"
- "Use `coding-agent` to implement the fix"
- "Use `reviewer-agent` to review this PR"
- "Use `commit-agent` to commit and push the changes"

### 2) Proactive (intent/keyword)

If no explicit subagent is named, infer the best match from the intent and keywords.

Keyword scoring table (strict mode, 0-5 scale):

| Subagent | Keyword examples | Score per match |
|---|---|---|
| `.github/agents/docker-ops-agent.md` | `make up-main`, `make logs-ollama`, `ps-main`, `gpu`, `nvidia-smi`, `compose` | 5 |
| `.github/agents/model-config-agent.md` | `LLM_CONFIG`, `workspace/configs`, `GGUF`, `mmproj`, `model_alias`, `chat_format` | 5 |
| `.github/agents/update-manager-agent.md` | `updates-check`, `updates-suggest`, `updates-apply`, `requirements-dev`, `LLAMA_CPP_VERSION`, `tools/update_manager.py` | 5 |
| `.github/agents/docs-sync-agent.md` | `README`, `CHANGELOG`, `docs`, `document`, `sync` | 4 |
| `.github/agents/coding-agent.md` | `implement`, `feature`, `refactor`, `fix bug`, `write tests`, `patch` | 3 |
| `.github/agents/reviewer-agent.md` | `review`, `code review`, `audit`, `risk`, `regression`, `missing tests` | 5 |
| `.github/agents/commit-agent.md` | `commit`, `git commit`, `push`, `commit and push`, `stage all`, `prepare commit` | 5 |

Tie-break rules:

1. Prefer exact command/file matches over generic words.
2. Prefer the subagent owning the file(s) the user explicitly mentions.
3. If scores tie across domains, ask one concise clarification question.

Minimum confidence threshold:

- Auto-route only when the best subagent score is `>= 5`.
- If best score is `< 5`, ask one concise clarification question before routing.

## Routing Decision Order

1. Honor explicit/manual routing request.
2. Otherwise, select the highest-confidence proactive match.
3. If work spans domains, run a primary subagent then secondary subagent(s) in sequence.
4. If ambiguous, ask one concise clarification question.
5. If no confident match, continue in orchestrator mode with global rules.

## Fallback and Escalation

- If a task exceeds a subagent boundary, hand back to orchestrator with:
  - current findings,
  - remaining tasks,
  - required next subagent (if obvious).
- If user intent changes mid-task, re-route using the same decision order.
