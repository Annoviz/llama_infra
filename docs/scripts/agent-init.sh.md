# agent-init.sh

## Purpose

Standardizes this repo's agent-harness configuration onto the agents-standard layout:

- **canonical content**: `.agents/{rules,skills,plans}(+agents)` + root `AGENTS.md`
- **harness dirs become relative directory symlinks** pointing back to canonical
  (e.g. `.claude/rules -> ../.agents/rules`), so every installed harness reads one source of truth

Supported harnesses: `claude`, `opencode`, `cursor`, `crush`, `hermes`. OpenCode, Crush and Hermes read
`AGENTS.md` natively (no alias file); only Claude gets a `CLAUDE.md -> AGENTS.md` link.

Full design contract: [../../.agents/plans/agent-init-overhaul-plan.md](../../.agents/plans/agent-init-overhaul-plan.md)
(scan → pre-flight matrix → report → approve; move-never-delete; idempotent).

## Usage

```bash
scripts/agent-init.sh --dry-run          # full scan + report, zero mutations (start here)
scripts/agent-init.sh                    # interactive: per-harness approval prompts
scripts/agent-init.sh --yes              # non-interactive: approves all; ABORTS (exit 1) if any blocking conflict exists
scripts/agent-init.sh -n claude,opencode # restrict to a harness subset
scripts/agent-init.sh --no-global        # skip the user-level (~) scan phase
```

Run from the repository root only. Exit codes: `0` ok/no-op · `1` blocked by conflict(s) · `2` fatal pre-condition · `3` aborted.

## Phases

1. **Scan** – detects installed harnesses (binary OR user config dir), classifies every link point (`OK / BROKEN / real content / external / missing`) and the entry file.
2. **Pre-flight matrix** – read-only conflict/corruption checks (`A` same-path/content, `B` links, `S` scope & frontmatter identity, `C` env). Block-severity items stop non-interactive runs before any mutation.
3. **Report + approval** – per-harness decision; blocking conflicts require explicit continue (interactive) or never proceed (`--yes`).
4. **Standard layer first** – ports legacy real content into `.agents/` (A2 winners kept, losers backed up), promotes a lone `CLAUDE.md`/`CRUSH.md` to `AGENTS.md`.
5. **Links** – creates `ln -srn` relative dir symlinks for approved harnesses only; correct links are never touched (idempotent).
6. **Git hygiene** – suggests marker-guarded `.gitignore` entries for untracked runtime files (e.g. `.opencode/package.json`, `.claude/settings.local.json`).
7. **Global scan** – user-level candidates (`~/.claude/rules` etc.) reported and, on approval, consolidated into `~/.agents/` with link-port; hermes' category skill tree and cursor's `.mdc` rules are excluded by design. Cross-scope divergence is never auto-merged (see contract §7-E).
8. **Summary** – per-harness outcome; machine-readable audit sidecar `agent-init-report.json` written to repo root (add to `.gitignore` if not versioning it).

## Guarantees & artifacts

- **Nothing is ever deleted**: real dirs/files replaced by links are moved to `.agent-init-backup/<UTC-timestamp>/` (created lazily — clean no-op runs leave the tree untouched).
- Existing *correct* symlinks are byte-for-byte untouched; a second run on a standardized repo makes zero file changes.
- Same-name content from several sources is never overwritten: highest-priority copy wins (`.agents` > claude > opencode > cursor > crush), losers land in the backup as `.conflict-*` copies.

## Verification

Regression sandbox (isolated git repos + mocked `HOME`/`PATH`, conflict fixtures included):

```bash
make tests-agent-init    # or: SUT="$PWD/scripts/agent-init.sh" bash scripts/tests/agent-init-tests/run_tests.sh
# expect ALL_GREEN, 46 assertions (fixtures in .agents/plans/agent-init-overhaul-plan.md §9)
```
