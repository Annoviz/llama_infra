#!/usr/bin/env bash
# Test runner for scripts/agent-init.sh — isolated sandboxes (git repo + fake HOME/PATH).
# Contract: .agents/plans/agent-init-overhaul-plan.md §9 (fixtures C-*)
# Usage: SUT=/path/to/agent-init.sh bash run_tests.sh   # expect ALL_GREEN, 46 assertions
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUT="${SUT:-$SCRIPT_DIR/scripts/agent-init.sh}"
ROOT_OVERRIDE=1
[[ -n "${AGENT_INIT_TEST_ROOT:-}" ]] && ROOT="$AGENT_INIT_TEST_ROOT" && ROOT_OVERRIDE=0
: "${ROOT:=$(mktemp -d "${TMPDIR:-/tmp}/agent-init-tests.XXXXXX")}"
[[ $ROOT_OVERRIDE == 0 ]] || trap 'rm -rf "$ROOT"' EXIT
PASS=0; FAIL=0; CASE=""

fail() { echo "ASSERT-FAIL [$CASE]: $*" >&2; FAIL=$((FAIL+1)); }
ok()   { PASS=$((PASS+1)); }
check()  { local d="$1"; shift; if "$@" >/dev/null 2>&1; then ok; else fail "$d (cmd: $*)"; fi; }
ncheck() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then fail "NOT-expected: $d"; else ok; fi; }

mkstub() { printf '#!/bin/sh\nexit 0\n' > "$MOCKBIN/$1" && chmod +x "$MOCKBIN/$1"; }

newcase() {
  CASE="$1"
  T="$ROOT/$CASE"
  mkdir -p "$T/repo" "$T/home" "$T/bin"
  MOCKBIN="$T/bin"; MOCKHOME="$T/home"
  cd "$T/repo" || exit 1
  git init -q . && git config user.email t@t && git config user.name t
  cp "$SUT" ./agent-init.sh
}

runit() { # non-interactive SUT run with mock env (timeout-guarded); appends --yes
  ( export HOME="$MOCKHOME" AGENT_INIT_HOME="$MOCKHOME"; unset XDG_CONFIG_HOME HERMES_HOME
    cd "$T/repo" && PATH="$MOCKBIN:$PATH" timeout 120 bash ./agent-init.sh --yes "$@" >"$T/out.log" 2>&1 )
  RC=$?
}

tree_sig() {
  ( find . -path ./node_modules -prune -o -type f -print0 2>/dev/null | grep -zv agent-init-report.json \
      | xargs -0 sha256sum 2>/dev/null
    find .claude .opencode .cursor .crush -maxdepth 3 -type l -printf '%p -> %l\n' 2>/dev/null ) | sha256sum | cut -d' ' -f1
}

# ================================================================ E0: empty dir, all harnesses installed
newcase E0; for b in claude opencode cursor crush hermes; do mkstub $b; done
runit
check "AGENTS.md stub created" test -f AGENTS.md
for d in rules skills plans; do check ".agents/$d created" test -d ".agents/$d"; done
for L in .claude/rules .claude/skills .claude/plans .opencode/rules .opencode/skills .opencode/plans .cursor/rules .cursor/skills .crush/skills; do
  check "symlink $L exists" test -L "$L"
done
check "CLAUDE.md -> AGENTS.md (bare relative)" bash -c '[ "$(readlink CLAUDE.md)" = AGENTS.md ]'
rel=1
for L in .claude/rules .opencode/skills .cursor/skills .crush/skills; do [ -L "$L" ] && case "$(readlink "$L")" in /*) rel=0;; esac; done
[ $rel = 1 ] && ok || fail "links must be RELATIVE (ln -sr), got absolute"
ncheck "CRUSH.md not created" test -e CRUSH.md
check ".claude/rules resolves to canonical" bash -c '[ "$(readlink -f .claude/rules)" = "$PWD/.agents/rules" ]'
( export HOME="$MOCKHOME" AGENT_INIT_HOME="$MOCKHOME"; unset XDG_CONFIG_HOME HERMES_HOME
  cd "$T/repo" && PATH="$MOCKBIN:$PATH" timeout 120 bash ./agent-init.sh --dry-run >"$T/dry.log" 2>&1 )
ncheck "no phantom agents link planned (no canonical agents dir)" grep -q 'link \.claude/agents' "$T/dry.log"
if grep -E '^[[:space:]]+[a-z]+ +(link|re-point|replace) [^ ]+ -> ' "$T/dry.log" | grep -vq 'entry link'; then fail "phantom plan entries in dry-run"; else ok; fi

# ================================================================ L1: claude-only legacy → standard first, then links
newcase L1; mkstub claude
mkdir -p .claude/rules .claude/skills/my-skill
printf 'rule one\n' > .claude/rules/rule-a.md
printf -- '---\nname: my-skill\ndescription: d\n---\nbody\n' > .claude/skills/my-skill/SKILL.md
printf 'legacy claude entry\n' > CLAUDE.md
runit
check "AGENTS.md == promoted legacy content" bash -c '[ "$(cat AGENTS.md)" = "legacy claude entry" ]'
check "CLAUDE.md is now the AGENTS.md symlink" bash -c '[ -L CLAUDE.md ] && [ "$(readlink CLAUDE.md)" = AGENTS.md ]'
check ".agents/rules/rule-a.md ported (standard built BEFORE link)" test -f .agents/rules/rule-a.md
check ".agents/skills/my-skill/SKILL.md ported" test -f .agents/skills/my-skill/SKILL.md
check ".claude/rules resolves to canonical" bash -c '[ "$(readlink -f .claude/rules)" = "$PWD/.agents/rules" ]'
check "old real dir evacuated to backup, not deleted" find .agent-init-backup -type d -name 'src-*.claude_rules' | grep -q .

# ================================================================ P1: broken link + real content (opencode+cursor)
newcase P1; mkstub opencode; mkstub cursor
mkdir -p .agents/plans && touch .agents/plans/p.md
mkdir -p .opencode
ln -s ../.agents/nosuch .opencode/rules            # BROKEN: target category absent
mkdir -p .cursor/skills/old-skill && printf 'skill body\n' > .cursor/skills/old-skill/SKILL.md
runit
check ".opencode/rules repaired to canonical" bash -c '[ "$(readlink -f .opencode/rules)" = "$PWD/.agents/rules" ]'
check "realdir content ported" test -f .agents/skills/old-skill/SKILL.md
check ".cursor/skills now a symlink" test -L .cursor/skills
ncheck ".cursor/agents link created (unverified convention — must NOT)" test -e .cursor/agents

# ================================================================ X1: crush not installed → port-only, no links/files
newcase X1; mkstub claude                            # crush deliberately absent from bin+home
mkdir -p .crush/skills/cs && printf 'cs\n' > .crush/skills/cs/SKILL.md
runit
check "crush skill content still ported (content preserved)" test -f .agents/skills/cs/SKILL.md
ncheck "CRUSH.md created for uninstalled harness" test -e CRUSH.md
ncheck ".crush re-created with links" bash -c '[ -L .crush/skills ]'
check "report file written" test -s agent-init-report.json

# ================================================================ R1: idempotency — two runs from empty, all installed
newcase R1; for b in claude opencode cursor crush hermes; do mkstub $b; done
runit; s1=$(tree_sig)
runit; s2=$(tree_sig)
[ "$s1" = "$s2" ] && ok || fail "re-run idempotency: content/link signature changed between pass 1 and 2"
check "second run exits 0" test $RC -eq 0

# ================================================================ CA2: A2 block, non-interactive → abort before ANY mutation
newcase CA2; mkstub claude; mkstub opencode
mkdir -p .claude/skills/shared .opencode/skills/shared
printf 'claude copy\n' > .claude/skills/shared/SKILL.md
printf -- '---\nname: shared\ndescription: d\n---\noc copy\n' > .opencode/skills/shared/SKILL.md
runit
[ $RC -eq 1 ] && ok || fail "expected exit 1 (block abort), got $RC"
grep -q '"code":"A2"' agent-init-report.json 2>/dev/null && ok || fail "A2 not in report"
ncheck ".agents mutated on blocked run" test -f .agents/skills/shared/SKILL.md
ncheck "AGENTS.md created on blocked run" test -f AGENTS.md

# ================================================================ CA3: file at dir-expected link point → A3 block
newcase CA3; mkstub claude
mkdir -p .claude && printf 'i am a file\n' > .claude/rules     # regular FILE where rules-dir expected
runit
grep -q '"code":"A3"' agent-init-report.json 2>/dev/null && ok || fail "A3 not in report"
[ $RC -eq 1 ] && ok || fail "expected exit 1, got $RC"
check ".claude/rules left untouched" bash -c '[ "$(cat .claude/rules)" = "i am a file" ]'

# ================================================================ CB1: dangling symlink inside port source → B1 block
newcase CB1; mkstub claude
mkdir -p .claude/skills && ln -s ../../vanished .claude/skills/dangle.md
runit
grep -q '"code":"B1"' agent-init-report.json 2>/dev/null && ok || fail "B1 not in report"
[ $RC -eq 1 ] && ok || fail "expected exit 1, got $RC"

# ================================================================ CB2: symlink cycle inside port source → B2 block, must terminate
newcase CB2; mkstub claude
mkdir -p .claude/skills/cyc
( cd .claude/skills && ln -s b.md cyc/a.md )
( cd .claude/skills/cyc && ln -s a.md b.md )
runit
[ $RC -eq 1 ] && ok || fail "expected exit 1 (B2), got $RC"
grep -q '"code":"B2"' agent-init-report.json 2>/dev/null && ok || fail "B2 not in report"

# ================================================================ K1: basic port + evacuation, single file
newcase K1; mkstub claude
mkdir -p .claude/rules && printf 'x\n' > .claude/rules/one.md
runit
check "content ported to canonical" bash -c '[ "$(cat .agents/rules/one.md)" = x ]'
check "source evacuated (backup exists)" find .agent-init-backup -type d -name 'src-*.claude_rules' | grep -q .

echo ""
echo "==================================="
echo "PASS=$PASS FAIL=$FAIL"
echo "artifacts root: $ROOT  (per-case logs: <case>/out.log)"
[ "$FAIL" -eq 0 ] && echo ALL_GREEN || echo RED — inspect $ROOT/<case>/out.log
