# routing-smoke

## Purpose

Provide lightweight routing smoke cases to sanity-check manual and proactive subagent selection behavior.

## Owns

- Example prompts for expected subagent routing
- Quick checks for ambiguous wording and tie-break behavior
- Regression notes when trigger keywords are changed

## Triggers

Keywords and intents such as:

- "routing smoke"
- "keyword routing sanity check"
- "subagent routing examples"
- "routing regression"

## Workflow

1. Run `make verify-agent-routing` before reviewing examples.
2. Validate manual routing examples map to exact requested subagent names.
3. Validate proactive examples map to highest-confidence keyword scores.
4. For ambiguous prompts, ensure one concise clarification question is expected.

Smoke cases:

| Prompt | Expected route |
|---|---|
| "Use `commit-agent` to stage, commit, and push these edits" | `commit-agent` (manual explicit) |
| "AnythingLLM is down; check logs and GPU visibility" | `docker-ops-agent` |
| "Add a new GGUF config and set model_alias" | `model-config-agent` |
| "Run updates-check and prepare a proposal" | `update-manager-agent` |
| "Implement a bug fix and patch tests" | `coding-agent` |
| "Review this PR for regressions and missing tests" | `reviewer-agent` |
| "Sync README and CHANGELOG for this workflow change" | `docs-sync-agent` |
| "Help with deployment and docs" | Clarify (cross-domain ambiguity) |

Clarification question smoke case:

| Prompt | Expected response |
|---|---|
| "Help with deployment and docs" | Clarification question: "Should I prioritize deployment triage (`docker-ops-agent`) or docs synchronization (`docs-sync-agent`)?" |

Negative smoke cases (should avoid this route):

| Prompt | Avoid route | Why |
|---|---|---|
| "Only review this patch; do not modify files" | `coding-agent` | Request is analysis-first, so use `reviewer-agent`. |
| "Please implement this fix directly" | `reviewer-agent` | Request is implementation-first, so use `coding-agent`. |
| "Explain model_alias and chat_format fields" | `docker-ops-agent` | This is model config guidance, so use `model-config-agent`. |
| "Just commit and push these staged files" | `update-manager-agent` | No version-management task; use `commit-agent`. |
| "Find newest tags and update requirements" | `commit-agent` | This is dependency automation, so use `update-manager-agent`. |
| "Restart services and inspect logs" | `docs-sync-agent` | This is operations triage, so use `docker-ops-agent`. |
| "Only refresh README and CHANGELOG notes" | `model-config-agent` | This is documentation sync, so use `docs-sync-agent`. |

## Boundaries

- This file is a QA/reference aid and not a task execution subagent.
- When routing rules are changed in `AGENTS.md`, update these cases in the same change.
- When prompts require execution, hand off to the matched execution subagent.

## Handoff Back

Return to orchestrator with:

- prompts checked,
- expected route per prompt,
- any mismatches with current scoring rules,
- suggested keyword-table updates.

## Example Prompt

"Use routing-smoke to sanity-check which subagent should handle these five prompts."

