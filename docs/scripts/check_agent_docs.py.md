# check_agent_docs.py

## Purpose

Validate Markdown subagent docs under `.github/agents/`. Enforces a simple heading contract for subagent files so routing instructions stay uniform and discoverable.

## Usage

```bash
python3 tools/check_agent_docs.py
make check-agent-docs
```

## Validation Rules

Each subagent file must include these headings:
- `# <Agent Name>`
- `## Purpose`
- `## Owns`
- `## Triggers`
- `## Workflow`
- `## Boundaries`
- `## Handoff Back`
- `## Example Prompt`

## AGENTS.md Validation

The script also validates that `AGENTS.md` contains all required agent definitions and checks for duplicates.

## Exit Codes

- `0` - All docs pass validation
- `1` - One or more validation failures

## See Also

- [../../AGENTS.md](../../AGENTS.md) - Agent routing and definitions
- [../operations.md](../operations.md) - Code quality checks
