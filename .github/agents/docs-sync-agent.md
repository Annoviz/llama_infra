# docs-sync-agent

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

## Handoff Back

Return to orchestrator with:

- docs files updated,
- what changed in user guidance,
- any detected implementation/documentation gaps.

## Example Prompt

"Use docs-sync-agent to align `README.md` and `CHANGELOG.md` after a workflow change in `AGENTS.md`."

