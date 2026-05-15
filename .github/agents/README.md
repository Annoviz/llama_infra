# agents-index

## Purpose

Provide a validated directory index for Markdown subagents and the required heading contract.

## Owns

- Directory-level guidance for `.github/agents/*.md`
- Required section contract used by `tools/check_agent_docs.py`
- Quick index of currently available subagent specs

## Triggers

Keywords and intents such as:

- "which subagents exist"
- "agent markdown convention"
- "required headings"
- "check agent docs"

## Workflow

1. Keep this index aligned with current subagent files.
2. Ensure each subagent file includes the required headings.
3. Validate structure with `make check-agent-docs`.
4. If required headings change, update both this file and the checker script.
5. Review trigger keywords monthly and prune overlaps that reduce routing confidence.

Current subagents:

- `docker-ops-agent.md`
- `model-config-agent.md`
- `update-manager-agent.md`
- `docs-sync-agent.md`
- `coding-agent.md`
- `reviewer-agent.md`
- `commit-agent.md`

Routing QA reference:

- `routing-smoke.md` (non-execution positive/negative smoke cases for routing behavior)

## Boundaries

- This file is index/convention guidance only; it does not own task execution policies.
- Cross-cutting orchestration rules remain in top-level `AGENTS.md`.

## Handoff Back

Return to orchestrator with:

- the current list of subagents,
- any heading-contract mismatch,
- any required docs/checker updates.

## Example Prompt

"Use agents-index to show required subagent headings and how to validate them locally."

