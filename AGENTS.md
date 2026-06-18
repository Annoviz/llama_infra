# AGENTS.md - Router and Global Rules for llama_infra

This file is the top-level orchestrator for agent behavior in this repo.

Detailed, task-specific guidance is delegated to Markdown subagents in
`.github/agents/`.

## Architecture Snapshot

Two independent Docker stacks are supported:

1. Main stack (`compose/main/*.yml`, assembled via `Makefile`): Ollama + AnythingLLM + Open WebUI (+ optional FalkorDB MCP services)
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
8. When routing rules or subagent docs change, run `make verify-agent-routing` before handoff.
9. End each agent session with 1-3 actionable improvements to the agent workflow.

## Subagent Discovery Convention

- All subagent definitions are in this file: [AGENTS.md](AGENTS.md)
- The router validates structure with `tools/check_agent_docs.py`.
- Each subagent section includes these headings:
  - `### <Agent Name>`
  - `## Purpose`
  - `## Owns`
  - `## Triggers`
  - `## Workflow`
  - `## Boundaries`
  - `## Handoff Back`
  - `## Example Prompt`

**Note:** Individual subagent markdown files have been archived to `.github/agents/archive/`.

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
| `docker-ops-agent` | `make up-main`, `make logs-ollama`, `ps-main`, `gpu`, `nvidia-smi`, `compose` | 5 |
| `model-config-agent` | `LLM_CONFIG`, `workspace/models`, `GGUF`, `mmproj`, `model_alias`, `chat_format` | 5 |
| `update-manager-agent` | `updates-check`, `updates-suggest`, `updates-apply`, `requirements-dev`, `LLAMA_CPP_VERSION`, `tools/update_manager.py` | 5 |
| `docs-sync-agent` | `README`, `CHANGELOG`, `docs`, `document`, `sync` | 4 |
| `coding-agent` | `implement`, `feature`, `refactor`, `fix bug`, `implementation`, `patch` | 3 |
| `reviewer-agent` | `review`, `code review`, `audit`, `risk`, `regression`, `missing tests` | 5 |
| `commit-agent` | `commit`, `git commit`, `push`, `commit and push`, `stage all`, `prepare commit` | 5 |

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

## Subagent Definitions

### docker-ops-agent

## Purpose

Handle Docker stack lifecycle tasks, service status checks, logs, and GPU smoke checks for this repository.

## Owns

- `Makefile` targets for main and llama.cpp stacks
- Compose render checks (`make config-main`, `make config-llama`, `make config-all`)
- Service state checks (`make ps-main`, `make ps-llama`, `make ps-all`)
- Logs and restart workflows (`make logs-*`, `make restart-*`)
- GPU checks (`make gpu-host`, `make gpu-smoke-llamacpp`)

## Triggers

Keywords and intents such as:

- "start/stop services"
- "compose config"
- "logs-ollama"
- "open-webui down"
- "AnythingLLM not starting"
- "GPU check"
- "nvidia-smi"

## Workflow

1. Prefer `make` targets over direct Docker commands when available.
2. Run config rendering checks before start/restart changes.
3. For startup issues, inspect logs immediately.
4. For GPU issues, run host check then container smoke test.
5. Provide concise remediation and the next verification command.

## Boundaries

- Do not edit model JSON internals unless needed only for basic path validation.
- Do not perform dependency/version bump logic owned by `update-manager-agent`.
- Do not skip documentation sync when workflows change.
- When the task is a pure code implementation request, route to `coding-agent`.

## Handoff Back

Return to orchestrator with:

- services touched,
- checks executed,
- unresolved errors,
- suggested next subagent (if needed).

## Example Prompt

"Use docker-ops-agent to diagnose why `open-webui` is down, check logs, and suggest the next make command."

---

### model-config-agent

## Purpose

Handle model configuration and llama.cpp Python server wiring for JSON config-driven model serving.

## Owns

- `workspace/models/*.json`
- `LLM_CONFIG` usage patterns
- Model path conventions under `/models/...`
- `model_alias`, `chat_format`, multimodal `clip_model_path`
- Guidance for adding new model config files

## Triggers

Keywords and intents such as:

- "add model config"
- "LLM_CONFIG"
- "config.json"
- "GGUF"
- "mmproj"
- "model_alias"
- "chat_format"
- "model file not found"

## Workflow

1. Verify expected config file and schema fields.
2. Validate path conventions for mounted `/models` files.
3. Confirm alias and format values match model family.
4. Suggest minimal config changes and deployment command.
5. Include a quick verification step for inference readiness.

## Boundaries

- Do not manage image tag/package updates owned by `update-manager-agent`.
- Do not own stack lifecycle remediation beyond config-specific checks.
- Keep broad docs updates delegated to `docs-sync-agent`.
- When the request is a generic code refactor unrelated to model config, route to `coding-agent`.

## Handoff Back

Return to orchestrator with:

- config files changed,
- model paths validated,
- launch command used,
- any unresolved runtime mismatch.

## Example Prompt

"Use model-config-agent to add a new multimodal config with GGUF and mmproj paths, then show the `LLM_CONFIG` launch command."

---

### update-manager-agent

## Purpose

Own version and dependency update workflows driven by `tools/update_manager.py` and managed defaults in compose/Dockerfile/requirements files.

## Owns

- `tools/update_manager.py`
- `tests/test_update_manager.py`
- `requirements-dev.txt` managed package bumps
- Compose/Dockerfile managed version defaults referenced by update manager
- `make updates-check`, `make updates-suggest`, `make updates-apply`

## Triggers

Keywords and intents such as:

- "update manager"
- "updates-check"
- "updates-apply"
- "bump docker tags"
- "requirements-dev"
- "LLAMA_CPP_VERSION"
- "proposal json"

## Workflow

1. Discover current and latest targets via update-manager commands.
2. Keep `workspace/requirements.txt` frozen (never auto-edit).
3. Apply only managed replacement points.
4. Run/update relevant tests when script behavior changes.
5. Summarize applied updates and compatibility notes.

## Boundaries

- Do not own model JSON tuning beyond dependency implications.
- Do not own generic service incident triage.
- Coordinate docs updates via `docs-sync-agent`.
- When the task is only commit/push operations, route to `commit-agent`.

## Handoff Back

Return to orchestrator with:

- updates discovered,
- updates applied,
- tests run,
- follow-up risk notes.

## Example Prompt

"Use update-manager-agent to run `updates-check`, prepare a proposal, and summarize safe updates without touching `workspace/requirements.txt`."

---

### docs-sync-agent

## Purpose

Keep repository documentation aligned with implementation changes, with special attention to `README.md` and `CHANGELOG.md`.

## Owns

- `README.md` workflow and usage docs
- `CHANGELOG.md` entries for behavior/config/version changes
- Documentation sections related to subagent routing and conventions

## Triggers

Keywords and intents such as:

- "update docs"
- "sync changelog"
- "README mismatch"
- "document new workflow"
- "agent conventions"

## Workflow

1. Identify user-visible or workflow-visible changes.
2. Update `README.md` usage guidance where needed.
3. Add dated `CHANGELOG.md` entry with concise impact notes.
4. Ensure examples match current Makefile-driven workflow.
5. Confirm links and file references are valid.

## Boundaries

- Do not make infra or code behavior changes beyond docs.
- If docs reveal implementation inconsistency, hand off to the owning subagent.
- When the user asks for review findings (not doc edits), route to `reviewer-agent`.

## Handoff Back

Return to orchestrator with:

- docs files updated,
- what changed in user guidance,
- any detected implementation/documentation gaps.

## Example Prompt

"Use docs-sync-agent to align `README.md` and `CHANGELOG.md` after a workflow change in `AGENTS.md`."

---

### coding-agent

## Purpose

Implement and modify repository code with safe, scoped changes aligned to existing conventions.

## Owns

- Feature implementation and refactors in tracked source files
- Small bug fixes and associated test updates
- Local validation commands tied to changed code paths
- Change notes describing what changed and why

## Triggers

Keywords and intents such as:

- "implement"
- "add feature"
- "refactor"
- "fix bug"
- "implementation"
- "patch"

## Workflow

1. Confirm scope and target files.
2. Implement minimal, focused edits.
3. Add or update tests when behavior changes.
4. Run relevant local validation.
5. Report files changed, validation, and next steps.

## Boundaries

- Do not own environment stack operations (`docker-ops-agent`).
- Do not own version-bump automation (`update-manager-agent`).
- Route documentation-only work to `docs-sync-agent`.
- When the user primarily asks for review/audit findings, use `reviewer-agent` instead.

## Handoff Back

Return to orchestrator with:

- files changed,
- tests/commands run,
- unresolved risks,
- recommended follow-up subagent.

## Example Prompt

"Use coding-agent to implement a small feature and include matching tests."

---

### reviewer-agent

## Purpose

Review code and configuration changes for correctness, regressions, risk, and missing tests.

## Owns

- Code review findings with severity and file references
- Regression risk checks for behavior and workflow changes
- Test coverage and validation gap identification
- Open questions/assumptions that block confidence

## Triggers

Keywords and intents such as:

- "review"
- "code review"
- "audit"
- "risk"
- "regression"
- "missing tests"

## Workflow

1. Inspect changed files and identify high-impact risks first.
2. Report findings ordered by severity with file references.
3. Call out missing tests and validation gaps.
4. List open questions or assumptions.
5. Provide a short secondary summary after findings.

## Boundaries

- Focus on review output; avoid broad rewrites unless requested.
- Route implementation follow-ups to `coding-agent`.
- Route docs-only updates to `docs-sync-agent`.
- When the user asks to apply code changes directly, route to `coding-agent`.

## Handoff Back

Return to orchestrator with:

- prioritized findings,
- testing gaps,
- explicit assumptions/questions,
- recommended remediation path.

## Example Prompt

"Use reviewer-agent to review this change for bugs, regressions, and missing tests."

---

### commit-agent

## Purpose

Handle git commit and push workflows safely after implementation and validation are complete.

## Owns

- Staging updated files for commit
- Creating clear commit messages that match repo conventions
- Pushing committed changes to the active branch/remote
- Reporting commit hash and push result

## Triggers

Keywords and intents such as:

- "commit"
- "git commit"
- "push"
- "commit and push"
- "stage all"
- "prepare commit"

## Workflow

1. Check `git status` and confirm intended files are included.
2. Stage requested files.
3. Create a focused commit message.
4. Push to the current branch remote.
5. Report commit id, branch, and push status.

## Boundaries

- Do not bypass validation checks when they are part of the requested workflow.
- Do not rewrite history unless explicitly requested.
- Do not force push unless explicitly requested.
- When there are unresolved implementation or review tasks, complete those before using this agent.

## Handoff Back

Return to orchestrator with:

- committed files,
- commit hash,
- branch and remote used,
- any push/authentication errors.

## Example Prompt

"Use commit-agent to commit and push all current changes after verification."

---

## Routing QA Reference (Smoke Cases)

### Positive Cases (Expected Routes)

| Prompt | Expected Route |
|---|---|
| "Use `commit-agent` to stage, commit, and push these edits" | `commit-agent` (manual explicit) |
| "AnythingLLM is down; check logs and GPU visibility" | `docker-ops-agent` |
| "Add a new GGUF config and set model_alias" | `model-config-agent` |
| "Run updates-check and prepare a proposal" | `update-manager-agent` |
| "Implement a bug fix and patch tests" | `coding-agent` |
| "Review this PR for regressions and missing tests" | `reviewer-agent` |
| "Sync README and CHANGELOG for this workflow change" | `docs-sync-agent` |
| "Help with deployment and docs" | Clarify (cross-domain ambiguity) |

### Clarification Question Cases

| Prompt | Expected Response |
|---|---|
| "Help with deployment and docs" | Clarification question: "Should I prioritize deployment triage (`docker-ops-agent`) or docs synchronization (`docs-sync-agent`)?"

### Negative Cases (Should Avoid This Route)

| Prompt | Avoid route | Why |
|---|---|---|
| "Only review this patch; do not modify files" | `coding-agent` | Request is analysis-first, so use `reviewer-agent`. |
| "Please implement this fix directly" | `reviewer-agent` | Request is implementation-first, so use `coding-agent`. |
| "Explain model_alias and chat_format fields" | `docker-ops-agent` | This is model config guidance, so use `model-config-agent`. |
| "Just commit and push these staged files" | `update-manager-agent` | No version-management task; use `commit-agent`. |
| "Find newest tags and update requirements" | `commit-agent` | This is dependency automation, so use `update-manager-agent`. |
| "Restart services and inspect logs" | `docs-sync-agent` | This is operations triage, so use `docker-ops-agent`. |
| "Only refresh README and CHANGELOG notes" | `model-config-agent` | This is documentation sync, so use `docs-sync-agent`. |
