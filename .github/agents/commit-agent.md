# commit-agent

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

