# Plan — `scripts/agent-init.sh` standardization overhaul (v2)

Status: **approved 2026-08-15** (design Q&A + conflict-matrix extension). This document is the
implementation contract; deviations require re-review.

## 1. Objective

Rewrite `scripts/agent-init.sh` so that a project (and, optionally, the user's home) standardizes
all agent-harness configuration onto the agents-standard layout:

- Canonical content lives in **`.agents/{rules,skills,plans}(,agents)`** + **`AGENTS.md`**.
- Each *installed* harness consumes it through **relative whole-directory symlinks** that are
  safe to commit at repo level.
- Everything is **scan → report → per-harness approval** before any mutation; no destructive ops;
  a full pre-flight conflict/corruption matrix runs read-only first.

## 2. Current-state findings (this repo)

| Item | State |
|---|---|
| Harnesses installed (detector = §4) | claude, opencode, cursor, hermes = yes; crush, codex = no |
| Already standardized | `AGENTS.md` canonical; `CLAUDE.md -> AGENTS.md`; `.claude/{plans,rules,skills}` and `.opencode/{plans,rules,skills}` are committed relative symlinks (mode 120000) into `.agents/` since commit `1104a8b`; both harness dirs share the same git tree |
| Script gaps | Unconditional links to all 4 old harnesses (creates `CRUSH.md`, `.config/crush/` even when crush is absent); no `plans/` handling; blind `rm -rf` + relink destroys working link trees; destructive `migrate_folder` (copy → `ln` without backup, can nest into real dirs); no scan/approve mode; `ln -s AGENTS.md CLAUDE.md` crashes under `set -e` on re-run |
| Git hygiene today | Root `.gitignore` has **no** harness entries. Clean status persists because: `.opencode/.gitignore` (self-ignoring, untracked) hides `node_modules`/`package*.json`; `~/.config/git/ignore` globally ignores `**/.claude/settings.local.json`. Fresh clones close neither gap until opencode re-runs locally → untracked noise |
| Concrete same-name collision found | `update-manager` exists in **two different formats**: `.opencode/skills/update-manager/SKILL.md` (plain) and the plugin skill under `.agents/skills/…` — real instance of matrix item A2 to exercise in tests |

## 3. Decision log (settled with user)

| # | Decision |
|---|---|
| D1 | "recursive symlinks (`ln -s -r`)" = **relative** whole-dir symlinks via `ln -srn`; replace real dir/file already at a link path by **move-to-backup → link**; never `rm`. Committed links must be relative-only (fresh-clone portable) |
| D2 | Installed = binary on PATH **OR** user-level config dir exists (§4) |
| D3 | User-level phase: `~/.agents/` canonical + **linkable real dirs only**; skip hermes category-style skills tree, cursor `.mdc`, harness settings files; **report-only with per-item approval** |
| D4 | `.gitignore`: **report-only suggestions**, applied on per-item approval (marker-guarded idempotent append) |
| D5 | Repo-level commit of links is intended → freshness/hygiene suggestions cover: committed non-self-ignoring `.opencode/.gitignore` + root ignores for `settings.local.json`/opencode node install |
| D6 | Full conflict/corruption matrix (§7) runs read-only pre-mutation; block-severity items stop the run under `--yes` |
| D7 | Hard-unresolvable conflicts across scopes **diverge**: materialize a real per-item-link directory at the deepest affected scope with hard copies of colliding entries, preserving the deep-wins cascade (harness precedence: nested-dir > project > user) |
| D8 | Canonical subagent container = `.agents/agents` (not `subagents`); per-harness target names come from §4 registry — no cross-harness assumption |

## 4. Harness registry (single source of truth, in-script array)

Canonical content dirs: `.agents/{rules,skills,plans,agents}` — **`agents`** is the canonical
container name for subagent definitions (rename from the old draft `subagents`; every verified
consumer expects `agents`). Created only when non-empty/portable content exists.

| Harness | Installed detector | Project entry file | Project link points → `.agents/` | Global (user-level) candidates | Convention source |
|---|---|---|---|---|---|
| claude | `command -v claude` ‖ `-d ~/.claude` | `CLAUDE.md → AGENTS.md` | `.claude/{rules,skills,plans}` + **`.claude/agents → agents`** if non-empty | `~/.claude/rules/` → `~/.agents/rules`; `~/.claude/skills/` → `~/.agents/skills` (plain md/SKILL.md ✔); skip `settings.json`, `projects/`, caches, `agent-memory*/` | official docs (code.claude.com sub-agents): `.claude/agents/` + `~/.claude/agents/`, recursive scan, identity = frontmatter `name` |
| opencode | `command -v opencode` ‖ `-d ~/.config/opencode` | *(reads `AGENTS.md` natively)* | `.opencode/{rules,skills,plans}` + **`.opencode/agents → agents`** if non-empty (singular `agent/` also accepted by loader) | global dirs under `~/.config/opencode/{agent(s),skills,rules}` if present (none today) | binary strings: `.opencode/agent/*.md OR .opencode/agents/*.md`; skills = recursive `**/SKILL.md`; commands `.opencode/command/*.md` out of scope |
| cursor | `command -v cursor` ‖ `-d ~/.cursor` | — | `.cursor/{rules,skills}` (**no agents link** — no verified project-level subagent convention; add to registry only when docs confirm) | `~/.cursor/rules` = **`.mdc` format → report-only skip (reason)**; `agents/`, `skills-cursor/` same until format verified | docs pages 404'd during planning (`/docs/agents`, `/llms.txt`); user-level `~/.cursor/agents/` exists but empty; ecosystem signal: crush also loads `.cursor/skills`, supporting that dir name |
| crush | `command -v crush` ‖ `-d ~/.config/crush` | *(reads `AGENTS.md` natively — `initialize-as AGENTS.md` default)* | **`.crush/skills → skills`** if non-empty (loads `.agents/skills`, `.claude/skills`, `.cursor/skills` too); legacy real `CRUSH.md` → port content per A6, no CRUSH.md link created | shared generic context **`~/.config/AGENTS.md`** (first-class candidate!); crush-specific `~/.config/crush/CRUSH.md` report-only; global skills `~/.config/{agents,crush}/skills`, `~/.agents/skills`, `~/.claude/skills`; **`crushrc` = executable bash → never touch/link** | official README (charmbracelet/crush): skill paths, global context files, security note that crushrc/crush.json are trusted code |
| hermes | `command -v hermes` ‖ `-d ${HERMES_HOME:-~/.hermes}` | *(reads `AGENTS.md` natively)* | — (AGENTS.md suffices; no extra dir) | `$HERMES_HOME/skills` **excluded** (category tree, hermes-managed); SOUL.md existence mention only | repo-local source inspection (`agent/` modules read AGENTS.md; HERMES_HOME env override) |

Content from a harness that exists in-project but is **not installed** is still *ported* into
`.agents/` (preserved), but gets no links and no entry file.

## 5. CLI & modes

```
agent-init.sh [--dry-run] [--yes] [-n claude,opencode] [--no-global] [--backup-dir DIR]
```

- `--dry-run`: run full pre-flight + report; mutate nothing. **Default when stdin is not a tty and `--yes` absent** (safe in CI/agents).
- `--yes`: auto-approve all proposals (still enforces block-severity aborts, D6).
- `-n/--harness`: restrict to listed harnesses.
- `--no-global`: skip Phase 6 (user-level scan).
- Exit codes: 0 ok / no-op; 1 blocked by conflict(s); 2 fatal pre-condition; 3 aborted/aborted-by-user.

## 6. Phase flow

```
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 0  args & env validation                                       │
│   git-repo-root check, cwd writable, bash>=5 or ln -r feature test   │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 1  SCAN (strictly read-only)                                   │
│   per harness: INSTALLED?                                            │
│   per link point: ✔ ok-symlink → .agents/* | ✖ broken/dangling      │
│        ▣ real-dir/real-file content (port candidate, resolved!)      │
│        · missing      + entry-file states (CLAUDE.md/CRUSH.md)       │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 2  PRE-FLIGHT CONFLICT/CORRUPTION MATRIX (§7) — read-only      │
│   emits full verdict list; dry-run stops here                        │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 3  REPORT + APPROVAL                                           │
│   status table; one prompt per INSTALLED harness with missing/      │
│   partial links or real content: [y/n/skip]; conflict items ask     │
│   individually (A2 etc.). --yes = auto-approve non-blockers         │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼  approved set only
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 4  BUILD STANDARD LAYER FIRST (requirement: standard before   │
│          link, even for legacy-only repos)                           │
│   mkdir -p .agents/{rules,skills,plans}(+agents only if content)   │
│   AGENTS.md: absent → stub; exactly one legacy entry file (real) →  │
│   promoted via atomic rename; many/differing → block A6             │
│   PORT real-dir content: NUL-safe walk, type-mismatch guard (A3),   │
│   dedup identical (A1), conflict-suffix differing (A2), stage→      │
│   `mv -T` atomic place, backup-first ordering (§7-E)                │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 5  LINK approved∩installed harnesses                           │
│   link_rel SRC DST: ✔ correct → skip (hard invariant)               │
│     DST real dir/file whose content ≠ SRC → mv to backup → ln -srn  │
│     DST missing/broken → ln -srn                                    │
│   entry files only for installed harnesses                           │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 6  GIT HYGIENE (report-only, per-item approval)               │
│   for each linked harness's runtime paths: git check-ignore probe    │
│   suggest: (a) commit minimal non-self-ignoring .opencode/.gitignore│
│            (node_modules, package.json, package-lock.json)          │
│            (b) root ignores: .claude/settings.local.json, opencode  │
│            node-install files — marker-guarded idempotent appends   │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 7  GLOBAL scan (~, unless --no-global)                        │
│   propose ~/.agents/ canonical + per-harness candidates (§4 col 5)  │
│   exclusions reasoned in-report; per-item y/n; move-to-backup then  │
│   ln -srn (never touch harness runtime files); backup in            │
│   ~/.agents-backup/<ts>/                                            │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 8  SUMMARY: linked / skipped / conflicts (reason codes) /     │
│          backup dirs / hygiene entries added                         │
└──────────────────────────────────────────────────────────────────────┘
```

Safety rails in all mutating phases: `set -euo pipefail`; every destructive op is a **move** to
`.agent-init-backup/<utc-timestamp>/` (project) — never a delete; two-phase writes (staging dir →
atomic `mv -T`) so a killed run leaves pre-state intact; per-item error trapping (one bad file ≠
abort the rest); all skips carry reason codes.

## 7. Pre-flight conflict & corruption matrix (Phase 2)

### A. Structural conflicts
| # | Detection | Severity | Action if unresolved |
|---|---|---|---|
| A1 | Same relative path in ≥2 port sources, **identical** content | info | auto-dedup, reported once |
| A2 | Same relative path in ≥2 port sources, **different** content | **block** | keep winner by priority (existing `.agents/` content > claude > opencode > cursor > crush); losers → backup as `<name>.conflict-<source>`; per-file prompt or skip |
| A3 | File-vs-directory type mismatch at same path | **block** | no auto-resolution; both stay untouched, reported |
| A4 | Case-folded name collisions (`Rule.md` + `rule.md`) | warn | kept distinct, flagged for human review |
| A5 | Source already a correct symlink into `.agents/` — **resolve symlinks before classifying content** | fatal-if-missed | short-circuit "no port" (prevents self-copy loops, e.g. AGENTS.md→AGENTS.md) |
| A6 | ≥2 real legacy entry files (CLAUDE.md + CRUSH.md), differing content | **block** | stop; user picks winner or merges manually; identical → dedup |

### B. Link integrity
| # | Detection | Severity | Action |
|---|---|---|---|
| B1a | dangling symlink **at a link point** | warn, auto-repair | stale pointer holds no data → old link backed up + repointed on approved run (refinement from v2 review: blocking here contradicted E5's BROKEN-repair) |
| B1b | dangling symlink **inside a port source** | block-per-item | excluded from porting (`EXCLFILE`), reported; under `--yes` the run aborts before mutation |
| B2 | symlink loop/cycle (self-referential chain, depth > 40) | **block** | skip subtree, report |
| B3 | source-internal symlink escaping repo (absolute / `..` escape) | warn | port verbatim; flag fresh-clone portability risk; never rewrite |
| B4 | existing correct symlink would be touched | info | hard invariant: skip — guarantees idempotent no-op re-runs |
| B5 | symlinks in port set resolve outside repo / into sibling harness dirs (cross-harness aliasing) | block-per-item | report; never follow across scope without approval (prevents A5 self-copy variants) |

### C. Environment & safety
| # | Detection | Severity | Action |
|---|---|---|---|
| C1 | not a git repo root / cwd unwritable | fatal (exit 2) | refuse with message |
| C2 | read/write permission gaps on any scanned path | fatal-per-fs | pre-scan abort, list paths |
| C3 | `bash <5` or no `ln -r` support (busybox etc.) | fatal | feature-detect once, exit 2 with hint |
| C4 | non-UTF8 / newline / space-heavy names in port set | warn | proceed only via NUL-safe pipelines; affected paths listed |
| C5 | free-space headroom for staged copy + backup | warn/fatal | `df` check before mutation |
| C6 | planned move target is a mounted volume or an already-tracked path with local diffs | **block** | report before any mv |

### D. Execution-safety invariants (Phases 4–5)
1. Two-phase writes: staging dir → atomic rename (`mv -T`) for every file.
2. Backup-before-mutate ordering, always.
3. NUL-safe iteration (`find -print0`, `read -d ''`) — no word-split corruption.
4. Dry-run performs the **entire** pre-flight; zero verdicts may differ between dry-run and real run.
5. Under `--yes`: block-severity items abort (exit 1) with nothing mutated after the failing item; warn/info never block.
6. Every skip/block lands in the Phase 8 summary with its reason code (A2/B1/…).

### E. Scope model & hard-conflict divergence policy (D7)

**Scope ladder (shallow → deep):** user-level (`~/.agents/*`, per-harness global dirs) < project
(`.agents/*`) < nested subproject (inner `.claude/`/`.agents/` discovered by upward-walking loaders).
Precedence: **deepest wins** — matches Claude Code's documented nearest-dir-wins behavior
(`.claude/agents/` walking, `/doctor` duplicate detection) and is the only model all five harnesses
can honor without tool-side changes.

**Cross-scope duplicate detection (added to Phase 2, read-only):** for every (harness × category),
union of loaded entries from every scope in the ladder; any name appearing >1× with **different
content hashes** = cross-scope conflict `X1`. Same-hash duplicates are benign (info).

**Divergence procedure — hard-unresolvable conflicts never merge, they diverge:**
1. Identify deepest scope `D` and every shallower duplicate `Sᵢ` of the colliding name(s).
2. If a shallow scope is fully symlink-linked to its canonical tree (normal state), **materialize** it:
   replace the single dir-symlink with a real directory containing **per-item relative symlinks**
   into that scope's canonical, *except* the colliding entries.
3. At the deepest scope `D`, place a **hard copy** (regular file/dir, not a link) of each colliding
   entry from `D`'s own canonical source — this is the "keep a hard copy of the deepest-scope
   content" guarantee: even if shallow links are later repaired/removed, `D` still owns its content.
4. Result: exactly **one live path per name** per (harness × category) load view; deep-wins by
   construction, not by hoping at tool precedence quirks.
5. Invariant `I1`: after any run, no harness load set contains two same-named entries with
   different content hashes — verified mechanically in Phase 8.

**Why hard copy at deepest (not symlink):** deep entries often evolve independently; a link back to
the shallow canonical would silently adopt shallow edits and re-create the collision on the next
harness start. Hard copy + report forces an explicit human reconciliation later (both files stay,
one is authoritative by position).

**Worked example (real data):** `update-manager` skill exists as `.opencode/skills/update-manager`
(plugin-flavored) and would be ported from two sources → A2 fires at PORT time (intra-scope):
winner kept, loser backed up. Cross-scope variant: if user-level `~/.agents/skills/update-manager`
also existed with different content during Phase 7 → X1 fires; script materializes the project
`.opencode/skills/` dir as per-item links + hard copy of the project's own entry, leaves the global
link untouched at global level — opencode load set sees exactly one `update-manager`, the project's.

**Audit:** every divergence is recorded in `agent-init-report.json` (machine-readable sidecar next
to the backup dir; also printed in Phase 8 summary) — scope, name, content hashes, action taken.

### F. Additional mismatch classes found in v2 audit
| # | Mismatch | Severity | Solution |
|---|---|---|---|
| S1 (M1) | **frontmatter `name` collision**: two files with same `name:` field in one load tree — tools key identity by frontmatter, not filename → silent shadowing regardless of path | **block** (B5-style check at Phase 2) | list all colliding files; user renames via frontmatter or accepts loss of one. Same check across scopes during Phase 7 union scan |
| S2 (M2) | required frontmatter missing (`name`+`description` for agent/skill files) → tool may skip file with confusing runtime error | warn | report per file; content kept untouched (never auto-patched — frontmatter edits change semantics) |
| S3 (M4) | harness runtime state inside canonical/linked dirs (`.opencode/package.json`, `node_modules`, `.claude/settings.local.json`) that a *link-first* approach would commit or clobber | **block-per-link** | guard list checked before linking; link refused while unguarded state exists at the path → run hygiene suggestion (Phase 6) first, then relink |
| S4 | harness-managed subtree mixed with portable content (e.g. opencode plugin skill sitting beside user skills; `skills-cursor` auto-generated set) | warn | detect markers (`node_modules` sibling, generated-file patterns); managed entries excluded from port set by default — approval can override item-by-item |
| S5 | same entry file name served by two canonical sources (e.g. both `CLAUDE.md` and a repo-root harness expects it but content differs between scopes) | **block** per A6/X1 ladder | deepest-scope real file wins; shallower copies only as diverged hard backups |
| S6 | `.env`-driven paths in committed configs (opencode.json linked with absolute workspace path — user-level today) | warn (global phase) | report absolute-path links into `~`; recommend relative or per-machine override; never auto-rewrite |

### G. Verified-today baseline
All 8 existing symlinks ✔ (re-run must be a provable no-op), A2 fixture = `update-manager` dual-format skill, B/C clean on this machine, S3 pre-existing state already git-hygienized (verified via `git check-ignore`). See also §4 convention-source column for per-harness verification evidence.

## 8. Deliverables

| File | Change |
|---|---|
| `scripts/agent-init.sh` | full rewrite per §5–§7 |
| `.agents/plans/agent-init-overhaul-plan.md` | this document (committed as source of contract) |
| `docs/scripts/agent-init.sh.md` | phases, flags, harness table, Windows-checkout pitfall (symlinks → text files without `core.symlinks`), relative-symlink rule, repo-hygiene rationale, usage examples — matching existing `<script>.sh.md` convention |
| `docs/scripts/README.md` | index entry |
| `AGENTS.md` | one line under "Doc sources of truth": `.agents/*` + harness links managed by `scripts/agent-init.sh`; edit canonical only |
| `CHANGELOG.md` | entry per repo convention (`infra:` type) |

No pre-existing symlink in this repo needs changing: the script must verify them ✔ and no-op.

## 9. Verification plan

1. `bash -n scripts/agent-init.sh` (+ shellcheck if available).
2. **Sandbox matrix** in `scripts/tests/agent-init-tests/run_tests.sh` (`make tests-agent-init`; `AGENT_INIT_TEST_ROOT` keeps sandboxes for inspection), each case diff-asserted after run:
   - E0 empty dir → full standardization (AGENTS.md stub, `.agents` built first, links created even for harnesses not detected on the mocked PATH — installation state affects only report metadata)
   - L1 claude-only legacy (real `.claude/rules/*` + real `CLAUDE.md`) → `.agents` built **first**, then linked, CLAUDE.md promoted
   - P1 partial: one broken symlink + one real dir → selective repair of both
   - X1 crush absent from mocked PATH & config → no `CRUSH.md`, no `.config/crush`
   - R1 immediate re-run ⇒ zero changes (idempotency diff)
   - C-A2 same-name-diff-content pair (fixture incl. real `update-manager` shape) → winner + conflict-suffix backup
   - C-A3 file-vs-dir mismatch → both untouched, exit 1 under `--yes`
   - C-B1 (B1b) dangling link inside port source → excluded from porting, run blocked (exit 1 under `--yes`)
   - C-B2 symlink cycle → subtree skipped, no hang
   - C-S1 two skill files with same frontmatter `name:` in one tree → block, both listed
   - C-S3 link point pre-seeded with unignored runtime state (`package.json`) → link refused until hygiene applied (two-stage run)
   - X1 user-level + project-level same-name different-content skill → divergence: per-item materialized dir at project scope + hard copy of project entry; invariant I1 asserted in single-harness load view
   - K1 `kill -9` mid-port → pre-state intact (staging/atomicity proof)
3. **Fresh-clone test**: clone repo to `/tmp`, run `--dry-run` with throwaway `$HOME` + mocked harness PATH ⇒ report all ✔ links, zero destructive proposals; then real run ⇒ `git status` unchanged.
4. Global phase exercised against fake `$HOME` only; the user's real home is touched exclusively during interactive per-item approvals in Phase 7.

## 10. Execution order (post-approval)

1. Sandbox harness + §9-2 fixtures → iterate until green.
2. Rewrite `scripts/agent-init.sh`; docs, AGENTS.md note, CHANGELOG.
3. Dry-run on this repo → expect no-op report; show to user. Real run only if something actually needs fixing (expected: none).
4. Phase 7 global scan of real home → interactive per-item approvals.
5. Commit proposed as `infra: agent-init scan/approve/relative-link standardization` — **only if explicitly requested**.

## 11. Windows-checkout caveat (documented, accepted risk)

Committed mode-120000 blobs check out as real symlinks on Linux/macOS only. On Windows without
`core.symlinks`, targets materialize as plain text files (e.g. `CLAUDE.md` = one line
"AGENTS.md") → silently empty config. Accepted for this repo (Linux-only use); mitigation = docs
warning + the relative-only invariant in D1.
