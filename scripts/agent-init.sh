#!/usr/bin/env bash
# agent-init.sh — standardize agent-harness configuration onto agents-standard layout.
# Contract: .agents/plans/agent-init-overhaul-plan.md  (v2.0, approved 2026-08-15)
#
#   canonical : .agents/{rules,skills,plans}(+agents) + AGENTS.md
#   harnesses : claude, opencode, cursor, crush, hermes  (registry §4)
#   safety    : scan -> pre-flight matrix -> report -> approve; move-never-delete;
#               atomic placement via staged mv -T; idempotent re-runs are no-ops.
set -euo pipefail
shopt -s nullglob

VERSION="2.0.0"
CANON=".agents"
PRIORITY=(.agents claude opencode cursor crush)     # A2 winner order

DRY_RUN=0; YES=0; NO_GLOBAL=0; RESTRICT=""
TS="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_FILE="agent-init-report.json"
APPROVED=()
EVENTS=()                                            # "CODE|severity|detail"
BLOCK_COUNT=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]
  --dry-run           full scan + report, no mutations (default when stdin is not a tty)
  --yes               auto-approve all non-blocking proposals
  -n, --harness LIST  restrict to comma-separated subset: claude,opencode,cursor,crush,hermes
  --no-global         skip user-level (\$HOME) scan phase
  -h, --help          this help
Exit codes: 0 ok/no-op · 1 blocked by conflict(s) · 2 fatal pre-condition · 3 aborted
EOF
}
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --yes) YES=1 ;;
    --no-global) NO_GLOBAL=1 ;;
    -n|--harness) RESTRICT="${2:?-n needs a value}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

fatal() { echo "[FATAL] $*" >&2; exit 2; }
info()  { echo "$*"; }

ev() { # $1=code $2=severity(info|warn|block) $3=detail
  local sev="$2"
  EVENTS+=("$1|$sev|$3")
  case "$sev" in block) BLOCK_COUNT=$((BLOCK_COUNT+1)) ;; esac
}
jesc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

write_report() { # emits JSON sidecar + summary of events
  local code sev detail out="" first=1
  for line in ${EVENTS[@]+"${EVENTS[@]}"}; do
    IFS='|' read -r code sev detail <<<"$line"
    [ $first -eq 0 ] && out+=","$'\n'
    first=0
    out+="{\"code\":\"$code\",\"severity\":\"$sev\",\"detail\":\"$(jesc "$detail")\"}"$'\n'
  done
  {
    echo "{"
    echo "  \"tool\": \"agent-init\", \"version\": \"$VERSION\", \"ts\": \"$TS\","
    echo "  \"events\": ["$'\n'"$out"$'\n'"  ],"
    echo "  \"blocked\": $BLOCK_COUNT"
    echo "}"
  } > "$REPORT_FILE"
  local n=0 b=0 w=0
  for line in ${EVENTS[@]+"${EVENTS[@]}"}; do case "${line#*|}" in info*) :;; warn*) w=$((w+1));; block*) b=$((b+1));; esac; done
  n=${#EVENTS[@]}
  info ""
  info "→ Summary: $n event(s) — $b blocked, $w warnings; report written to $REPORT_FILE"
}

# ================================================================ phase 0 : guards
[ -d ".git" ] || fatal "C1|block|not a git repository root (cwd=$(pwd)); run from repo root"
command -v ln >/dev/null 2>&1 || fatal "C3|block|ln missing"
ln_ok=nope; _t=$(mktemp -d)
if ( cd "$_t" && touch src && mkdir d && ln -srn src d/tgt && [ -L d/tgt ] ); then ln_ok=yes; fi
rm -rf "$_t"
[ "$ln_ok" = yes ] || fatal "C3|block|GNU coreutils ln with --relative (-r) required"

HNAMES=(claude opencode cursor crush hermes)
if [ -n "$RESTRICT" ]; then
  IFS=',' read -ra HNAMES <<<"$RESTRICT"
  for h in "${HNAMES[@]}"; do
    case "$h" in claude|opencode|cursor|crush|hermes) ;; *) fatal "C1|block|unknown harness '$h'" ;; esac
  done
fi

hash_f() { sha256sum -- "$1" | awk '{print $1}'; }

# ================================================================ registry (contract §4)
declare -A DETECTOR LINKMAP ENTRYFILE
DETECTOR[claude]='command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ]'
DETECTOR[opencode]='command -v opencode >/dev/null 2>&1 || [ -d "$HOME/.config/opencode" ]'
DETECTOR[cursor]='command -v cursor >/dev/null 2>&1 || [ -d "$HOME/.cursor" ]'
DETECTOR[crush]='command -v crush >/dev/null 2>&1 || [ -d "$HOME/.config/crush" ]'
DETECTOR[hermes]='command -v hermes >/dev/null 2>&1 || [ -d "${HERMES_HOME:-$HOME/.hermes}" ]'

# link point "destrel:category"; dest relative to repo root; category under $CANON/
LINKMAP[claude]=".claude/rules:rules .claude/skills:skills .claude/plans:plans .claude/agents:agents"
LINKMAP[opencode]=".opencode/rules:rules .opencode/skills:skills .opencode/plans:plans .opencode/agents:agents"
LINKMAP[cursor]=".cursor/rules:rules .cursor/skills:skills"
LINKMAP[crush]=".crush/skills:skills"
LINKMAP[hermes]=""

# harnesses needing an AGENTS.md alias (crush/opencode/hermes read AGENTS.md natively)
ENTRYFILE[claude]="CLAUDE.md"; ENTRYFILE[opencode]="" ; ENTRYFILE[cursor]=""
ENTRYFILE[crush]=""          ; ENTRYFILE[hermes]=""

LEGACY_ENTRYFILES=(CLAUDE.md CRUSH.md)

# ================================================================ phase 1 : scan (read-only)
info "==== agent-init v$VERSION ===="
info "Phase 1: scanning workspace (read-only)"

declare -A INSTALLED LSTATE ESTATE EXT_TARGET
declare -a PORT_SOURCES=()      # entries "h<US>dest" — US = unit separator, never in paths

for h in "${HNAMES[@]}"; do
  if ( eval "${DETECTOR[$h]}" ) 2>/dev/null; then INSTALLED[$h]=1; else INSTALLED[$h]=0; fi

  for pair in ${LINKMAP[$h]}; do
    dest="${pair%%:*}"; catn="${pair##*:}"; key="$h|"$dest
    if [ -L "$dest" ]; then
      tgt="$(readlink -- "$dest")"
      tp="$(cd "$(dirname "$dest")" && pwd)/$tgt"
      if [ -e "$tp" ] && [ "$(realpath -- "$tp")" = "$(pwd)/$CANON/$catn" ]; then
        LSTATE[$key]=OK
      elif [ -e "$tp" ]; then
        LSTATE[$key]=EXT; EXT_TARGET[$key]="$tgt"; ev B3 warn "external symlink $dest -> $tgt (not pointing into $CANON/)"
      else
        LSTATE[$key]=BROKEN; ev B1 warn "dangling symlink at link point $dest (harness=$h) — stale pointer, auto-repointed on approval (old link backed up); inside-port-source dangles stay blocking (B1b)"
      fi
    elif [ -d "$dest" ]; then
      LSTATE[$key]=DIR; PORT_SOURCES+=("$h"$'\x1f'"$dest")
    elif [ -f "$dest" ]; then
      LSTATE[$key]=FILE; ev A3 block "regular file at directory-expected path $dest (harness=$h)"
    else
      LSTATE[$key]=MISSING
    fi
  done

  ef="${ENTRYFILE[$h]}"
  if [ -n "$ef" ]; then
    if   [ -L "$ef" ] && [ "$(readlink -- "$ef")" = "AGENTS.md" ] && [ -e "$ef" ]; then ESTATE[$h]=E_OK
    elif [ -L "$ef" ]; then ESTATE[$h]=E_EXT; EXT_TARGET["$h|ENTRY"]="$(readlink -- "$ef")"; ev A6 warn "entry file $ef is a symlink to $(readlink -- "$ef"), not AGENTS.md"
    elif [ -f "$ef" ];     then ESTATE[$h]=E_REAL
    else                        ESTATE[$h]=E_MISSING; fi
  fi
done

# ================================================================ port content model
declare -A SRCFILES      # rel -> newline-joined "hash label srcabsfile"
declare -a ALLRELS=()
rel_seen() { local r; for r in ${ALLRELS[@]+"${ALLRELS[@]}"}; do [ "$r" = "$1" ] && return 0; done; return 1; }

for pse in ${PORT_SOURCES[@]+"${PORT_SOURCES[@]}"}; do
  h="${pse%%$'\x1f'*}"; dest="${pse#*$'\x1f'}"
  while IFS= read -r -d '' f; do
    rel="${f#"$dest"/}"
    SRCFILES["$rel"]+=$(hash_f "$f")" $h $f"$'\n'
    rel_seen "$rel" || ALLRELS+=("$rel")
  done < <(find "$dest" -type f -print0 | sort -z)
done
if [ -d "$CANON" ]; then
  while IFS= read -r -d '' f; do
    rel="${f#"$CANON"/}"
    SRCFILES["$rel"]+=$(hash_f "$f")" .agents $f"$'\n'
    rel_seen "$rel" || ALLRELS+=("$rel")
  done < <(find "$CANON" -type f -print0 | sort -z)
fi

# B1/B2: symlink integrity inside port sources (dangling, cycles); S6 escape warns
declare -A EXCLFILE    # abs path -> reason code : excluded from porting on blocked runs
for pse in ${PORT_SOURCES[@]+"${PORT_SOURCES[@]}"}; do
  h="${pse%%$'\x1f'*}"; dest="${pse#*$'\x1f'}"
  while IFS= read -r -d '' f; do
    tgt="$(readlink -- "$f")"
    base="$(cd "$(dirname "$f")" && pwd)"
    if [ ! -e "$base/$tgt" ] && [ ! -L "$base/$tgt" ]; then
      ev B1 block "dangling symlink in port source: $f -> $tgt (harness=$h)"
      case "$f" in "$CANON"/*) : ;; *) EXCLFILE["$f"]=B1 ;; esac
      continue
    fi
    case "$tgt" in /*) ev B3 warn "absolute symlink escapes project on other machines: $f -> $tgt";; esac
    cur="$base/$tgt"; depth=0; cyc=0
    while [ -L "$cur" ] && [ $depth -lt 40 ]; do
      case "$(realpath -- "$PWD/$f" 2>/dev/null)" in *"$cur") cyc=1; break;; esac
      cur="$(cd "$(dirname "$cur")" && pwd)/$(readlink -- "$cur")"; depth=$((depth+1))
    done
    [ $depth -ge 40 ] && cyc=1
    if [ "$cyc" = 1 ]; then
      ev B2 block "symlink cycle/over-40 hops: $f (harness=$h)"
      case "$f" in "$CANON"/*) : ;; *) EXCLFILE["$f"]=B2 ;; esac
    fi
  done < <(find "$dest" -type l -print0 2>/dev/null | sort -z)
done

declare -A WINNER WINHASH
for rel in ${ALLRELS[@]+"${ALLRELS[@]}"}; do
  vals="$(printf '%s' "${SRCFILES[$rel]}" | awk 'NF{print}')"      # drop blank lines, no trailing NL
  labels="$(awk '{print $2}' <<<"$vals" | sort -u)"                  # single entry: herestring NL is the only one
  nlab=$(awk 'END{print NR}' <<<"$labels")
  nhash=$(awk '{print $1}' <<<"$vals" | sort -u | awk 'END{print NR}')
  if [ "$nhash" -le 1 ] && [ "$nlab" -eq 1 ]; then continue; fi
  winner=""
  for l in ${PRIORITY[@]+"${PRIORITY[@]}"}; do grep -qx -- "$l" <<<"$labels" && { winner="$l"; break; }; done
  WINNER[$rel]="$winner"
  WINHASH[$rel]="$(awk -v w="$winner" '$2==w{print $1; exit}' <<<"$vals")"
  if [ "$nhash" -gt 1 ]; then
    ev A2 block "same path differing content: $rel (winner=$winner; losers backed up, not merged)"
  else
    ev A1 info "identical duplicates deduped: $rel (sources: $(echo $labels | tr '\n' ' '))"
  fi
done

# A6 legacy entry files
A6STATE="none"; LEG_REAL=()
for ef in ${LEGACY_ENTRYFILES[@]+"${LEGACY_ENTRYFILES[@]}"}; do [ -f "$ef" ] && [ ! -L "$ef" ] && LEG_REAL+=("$ef"); done
case ${#LEG_REAL[@]} in
  0) : ;;
  1) A6STATE="promote:${LEG_REAL[0]}" ;;
  *) if [ "$(hash_f "${LEG_REAL[0]}")" = "$(hash_f "${LEG_REAL[1]}")" ]; then A6STATE="dedup"; else ev A6 block "conflicting legacy entry files: ${LEG_REAL[*]} — choose winner manually"; fi ;;
esac

# S1 frontmatter name collisions across all portable markdown
declare -A FRONT_SEEN S1_REPORTED
while IFS= read -r -d '' f; do
  nm="$(awk 'NR==1 && /^---[[:space:]]*$/{inf=1;next} inf && /^---[[:space:]]*$/{exit} inf{ if(match($0,/^name:[[:space:]]*/)){ s=$0; sub(/^name:[[:space:]]*/,"",s); gsub(/["'"'"']/,"",s); print s; exit } }' "$f")"
  [ -n "$nm" ] || continue
  if [ -z "${FRONT_SEEN[$nm]:-}" ]; then FRONT_SEEN["$nm"]="$f"
  else ev S1 block "frontmatter name '$nm' declared by both: ${FRONT_SEEN[$nm]} AND $f (identity collision, tool behavior undefined)"
       case "$f" in "$CANON"/*) : ;; *) EXCLFILE["$f"]=S1; EXCLFILE["${FRONT_SEEN[$nm]}"]=S1;; esac; fi
done < <( { for pse in ${PORT_SOURCES[@]+"${PORT_SOURCES[@]}"}; do d="${pse#*$'\x1f'}"; find "$d" -type f -name '*.md' -print0 2>/dev/null; done
           [ -d "$CANON" ] && find "$CANON" -type f -name '*.md' -print0 2>/dev/null || true; } )

# C-checks: read access on sources, writability on canonical target
for pse in ${PORT_SOURCES[@]+"${PORT_SOURCES[@]}"}; do
  d="${pse#*$'\x1f'}"; [ -r "$d" ] || ev C2 block "port source unreadable: $d"
done
if [ ! -w "." ]; then fatal "C2|block|repo root not writable"; fi

# ================================================================ phase 3 : report + approval
echo ""
echo "------------------- STATUS REPORT -------------------"
printf '%-10s %-9s %s\n' "harness" "installed" "link points (OK=✔ broken=✖ content=▣ ext=⇗ missing=·)"
for h in "${HNAMES[@]}"; do
  printf '%-10s %-9s' "$h"$([ "${INSTALLED[$h]}" = 1 ] && echo yes || echo no) ""
  pts=""
  for pair in ${LINKMAP[$h]}; do dest="${pair%%:*}"
    case "${LSTATE["$h|$dest"]:-MISSING}" in
      OK) pts+=" $dest:✔";; BROKEN) pts+=" $dest:✖";; DIR) pts+=" $dest:▣";; FILE) pts+=" $dest:■";; EXT) pts+=" $dest:⇗";; *) pts+=" $dest:·"
    esac
  done
  ef="${ENTRYFILE[$h]}"
  [ -n "$ef" ] && pts+="  entry($ef)=${ESTATE[$h]:-?}"
  echo "       | $pts"
done
[ -f AGENTS.md ] && echo "entry file AGENTS.md: present" || echo "entry file AGENTS.md: ABSENT (will be created)"
for line in ${EVENTS[@]+"${EVENTS[@]}"}; do
  IFS='|' read -r code sev detail <<<"$line"
  case "$sev" in block) printf '⛔ [%s] %s\n' "$code" "$detail";; warn) printf '⚠  [%s] %s\n' "$code" "$detail";; info) printf '·  [%s] %s\n' "$code" "$detail";; esac
done

needs_work() {
  local h="$1" pair dest ef
  for pair in ${LINKMAP[$h]}; do dest="${pair%%:*}"; catn="${pair##*:}"
    [ -d "$CANON/$catn" ] && case "${LSTATE["$h|$dest"]:-MISSING}" in MISSING|BROKEN|EXT|FILE) return 0;; esac; done
  ef="${ENTRYFILE[$h]}"
  [ -n "$ef" ] && case "${ESTATE[$h]:-E_MISSING}" in E_MISSING|E_REAL|E_EXT) return 0;; esac
  [ ! -f AGENTS.md ] && return 0
  return 1
}

declare -A DECISIONS
for h in ${HNAMES[@]+"${HNAMES[@]}"}; do
  if [ "${INSTALLED[$h]}" != 1 ]; then DECISIONS["$h"]="not-installed (content ported only)"; continue; fi
  if ! needs_work "$h"; then DECISIONS["$h"]="ok (already standardized)"; continue; fi
  if [ "$YES" -eq 1 ]; then DECISIONS["$h"]=approved
  elif [ -t 0 ]; then
    printf '\n   Harness %-9s — sync to standard? [Y/n] ' "$h"
    read -r ans; case "${ans:-Y}" in ""|y|Y) DECISIONS["$h"]=approved;; *) DECISIONS["$h"]=declined ;; esac
  else DECISIONS["$h"]="pending (non-interactive without --yes)"; fi
done

if [ ${BLOCK_COUNT} -gt 0 ]; then
  echo ""
  if [ "${DRY_RUN}" -eq 1 ]; then info "blocking conflicts present (dry-run stops after report)"; write_report; exit 1; fi
  if [ "$YES" -eq 1 ]; then info "⛔ blocking conflicts present with --yes — aborting before mutation (exit 1)"; write_report; exit 1; fi
  if [ ! -t 0 ]; then info "blocking conflicts present, non-interactive without --yes — running as dry-run report only (exit 1)"; write_report; exit 1; fi
  printf '   ⛔ %s blocking conflict(s) above. Continue with NON-blocked work anyway? [y/N] ' "$BLOCK_COUNT"
  read -r ans; case "${ans:-N}" in y|Y) : ;; *) info "aborted — resolve conflicts and re-run"; write_report; exit 3;; esac
fi

show_plan() { # dry-run: print exactly what a real run would create (same conditions as phase 5)
  echo ""
  info "--dry-run plan — mutations a real run WOULD perform:"
  if [ "$YES" -eq 0 ] && [ ! -t 0 ]; then printf '   (execution requires --yes or interactive approval; unapproved runs are no-ops)\n'; fi
  local h pair dest ef any=0
  for h in ${HNAMES[@]+"${HNAMES[@]}"}; do
    [ "${INSTALLED[$h]}" = 1 ] || continue
    for pair in ${LINKMAP[$h]}; do dest="${pair%%:*}" catn="${pair##*:}"
      [ -d "$CANON/$catn" ] || continue   # same condition as phase 5: no canonical category → no link planned/created
      case "${LSTATE["$h|$dest"]:-MISSING}" in
        MISSING) printf '   %-10s link %s -> %s/%s (new)\n' "$h" "$dest" "$CANON" "$catn"; any=1;;
        BROKEN)  printf '   %-10s re-point broken %s -> %s/%s (old link to backup)\n' "$h" "$dest" "$CANON" "$catn"; any=1;;
        EXT)     printf '   %-10s replace external %s -> %s/%s\n' "$h" "$dest" "$CANON" "$catn"; any=1;;
      esac
    done
    ef="${ENTRYFILE[$h]}"
    if [ -n "$ef" ] && case "${ESTATE[$h]:-E_MISSING}" in E_OK) false;; *) true;; esac; then
      printf '   %-10s entry link %s -> AGENTS.md\n' "$h" "$ef"; any=1
    fi
  done
  [ -f AGENTS.md ] || { info "   root        create AGENTS.md stub (standard entry point)"; any=1; }
  local catn
  for catn in rules skills plans; do [ -d "$CANON/$catn" ] || { printf '   root        mkdir %s/%s\n' "$CANON" "$catn"; any=1; }; done
  if [ "$any" = 0 ]; then info "   (none — workspace already fully standardized and idempotent)"; fi
}
[ "${DRY_RUN}" -eq 1 ] && show_plan

if [ "$DRY_RUN" -eq 0 ]; then
  for h in ${HNAMES[@]+"${HNAMES[@]}"}; do case "${DECISIONS[$h]:-}" in approved) APPROVED+=("$h");; esac; done
  if [ ${#APPROVED[@]} -eq 0 ]; then info "No harnesses approved — nothing to do."; write_report; exit 0; fi
fi

# backup dir is created LAZILY (only when a real mutation needs it) so no-op runs leave the tree untouched
BACKUP_DIR="$PWD/.agent-init-backup/$TS"
STAGE="$BACKUP_DIR/stage"
ensure_backup() { [ -n "${BACKUP_MADE:-}" ] && return 0; mkdir -p -- "$BACKUP_DIR" "$STAGE"; BACKUP_MADE=1; }

if [ "${DRY_RUN}" -eq 0 ]; then
# ============================== phase 4 : standard layer first (real run only)
echo ""
info "Phase 4: building canonical '$CANON/' layer (port content before linking)"
for catn in rules skills plans; do mkdir -p "$CANON/$catn"; done

case "${A6STATE}" in
  promote:*)
    srcf="${A6STATE#promote:}"
    if [ -e "AGENTS.md" ]; then
      ensure_backup
      mv -- "AGENTS.md" "$BACKUP_DIR/AGENTS.md.preexisting"
      if [ "$(hash_f "$srcf")" = "$(hash_f "$BACKUP_DIR/AGENTS.md.preexisting")" ]; then
        mv -- "$BACKUP_DIR/AGENTS.md.preexisting" "AGENTS.md"; rm -f -- "$srcf"
        info "   ↳ $srcf identical to existing AGENTS.md — duplicate removed."
      else
        cp -p -- "$srcf" "$BACKUP_DIR/${srcf}.conflict-copy"
        fatal "A6: legacy $srcf differs from existing AGENTS.md — merge manually (copy kept in backup), then re-run"
      fi
    else
      mv -- "$srcf" "AGENTS.md"; info "   ↳ Promoted $srcf -> AGENTS.md."
    fi ;;
  dedup)
    keep="${LEG_REAL[0]}"
    ensure_backup
    for ef in ${LEG_REAL[@]+"${LEG_REAL[@]}"}; do [ "$ef" = "$keep" ] && continue
      if [ ! -e "AGENTS.md" ]; then mv -- "$ef" "AGENTS.md"; else mv -- "$ef" "$BACKUP_DIR/dup-$ef"; fi
    done ;;
  conflict)
    ev A6 warn "legacy entry-file conflict deferred — no AGENTS.md promotion this run (choose winner manually)" ;;
  *)
    if [ ! -f AGENTS.md ]; then printf '# Universal Agent Configuration\n' > "AGENTS.md"; info "   ↳ Initialized fresh AGENTS.md."; fi ;;
esac

APPLIED=0; LOSED=0; KEPTCANON=0
  for pse in ${PORT_SOURCES[@]+"${PORT_SOURCES[@]}"}; do
  h="${pse%%$'\x1f'*}"; dest="${pse#*$'\x1f'}"
  case "${DECISIONS[$h]:-declined}" in approved|not-installed*) ;; *) continue;; esac
  ensure_backup
  catn="rules"
  for pair in ${LINKMAP[$h]}; do [ "${pair%%:*}" = "$dest" ] && catn="${pair##*:}"; done
  while IFS= read -r -d '' f; do
    if [ -n "${EXCLFILE[$f]:-}" ]; then ev "${EXCLFILE[$f]}" warn "excluded from porting (blocked item): $f"; continue; fi
    rel="${f#"$dest"/}"
    tgt="$CANON/$catn/$rel"
    fh=$(hash_f "$f"); wh="${WINHASH[$rel]:-}"
    if [ -e "$tgt" ]; then                            # canonical already owns this path
      if [ "$(hash_f "$tgt")" = "$fh" ]; then KEPTCANON=$((KEPTCANON+1)); continue; fi
      mv -- "$f" "$BACKUP_DIR/conflict-$(echo "$rel" | tr '/' '_').from-$h"; LOSED=$((LOSED+1)); ev A2 warn "loser copy backed up: $rel (from harness=$h)"; continue
    fi
    if [ -n "$wh" ] && [ "$fh" != "$wh" ]; then        # not the A2 winner
      mv -- "$f" "$BACKUP_DIR/conflict-$(echo "$rel" | tr '/' '_').from-$h"; LOSED=$((LOSED+1)); continue
    fi
    mkdir -p "$(dirname "$tgt")"
    if [ -L "$f" ]; then cp -P -- "$f" "$STAGE/x"; mv -T -- "$STAGE/x" "$tgt"
    else cp -p -- "$f" "$STAGE/x"; mv -T -- "$STAGE/x" "$tgt"; fi
    APPLIED=$((APPLIED+1))
  done < <(find "$dest" \( -type f -o -type l \) -print0 2>/dev/null | sort -z)
  # evacuate emptied real source dir (two-phase: files already moved above; only shells remain)
  left=0
  while IFS= read -r -d '' rem; do left=1; break; done < <(find "$dest" \( -type f -o -type l \) -print0 2>/dev/null)
  if [ "$left" = 0 ] && [ -d "$dest" ]; then
    mv -- "$dest" "$BACKUP_DIR/src-$(echo "$dest" | tr '/' '_')"
    rmdir -p --ignore-fail-on-non-empty "$(dirname "$dest")" 2>/dev/null || true
    info "   ↳ $dest content ported -> $CANON/$catn/ (old dir backed up)"
  elif [ -d "$dest" ]; then
    info "   ↳ PARTIAL: $dest still holds unportable entries — inspect $BACKUP_DIR and finish manually"
  fi
done
info "   ↳ canonical layer: $APPLIED file(s) ported, $LOSED conflict copies backed up, $KEPTCANON already-canonical kept."

# ================================================================ phase 5 : links (installed & approved only)
info ""
info "Phase 5: creating relative directory symlinks for approved harnesses"

link_rel() { # $1=source(path) $2=dest(location; file/dir name)
  local src="$1" dest="$2" base cur
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    base="$(cd "$(dirname "$dest")" && pwd)"
    if [ -L "$dest" ]; then
      cur="$(readlink -- "$dest")"
      if realpath -- "$base/$cur" >/dev/null 2>&1; then
        if [ "$(realpath -- "$base/$cur")" = "$(realpath -- "$src")" ]; then return 0; fi   # invariant: correct link untouched (B4)
      fi
    fi
    mv -- "$dest" "$BACKUP_DIR/relink-$(echo "${dest#"$PWD"/}" | tr '/' '_')"
  fi
  mkdir -p "$(dirname "$dest")"
  base="$(cd "$(dirname "$dest")" && pwd)"
  ( cd "$base" && ln -srn -- "$src" "${dest##*/}" ) || fatal "link failed: $dest -> $src"
  info "   ↳ linked ${dest#"$PWD"/} -> $( (cd "$base"); printf '%s' "$(realpath --relative-to="$base" "$src")" )"
}

for h in ${APPROVED[@]+"${APPROVED[@]}"}; do
  for pair in ${LINKMAP[$h]}; do
    dest="${pair%%:*}"; catn="${pair##*:}"
    [ -d "$CANON/$catn" ] || continue        # canonical category not created (no content) → skip link
    link_rel "$(pwd)/$CANON/$catn" "$(pwd)/$dest"
  done
   ef="${ENTRYFILE[$h]}"
   if [ -n "$ef" ]; then
     if [ ! -e "$PWD/$ef" ] || { [ -L "$PWD/$ef" ] && [ "$(readlink -- "$PWD/$ef")" != "AGENTS.md" ]; }; then
       link_rel "$(pwd)/AGENTS.md" "$(pwd)/$ef"
     fi
   fi
 done
fi # end real-run-only phases 4-5

# ================================================================ phase 6 : git hygiene (report-only → per-item)
info ""
info "Phase 6: git hygiene probes (suggestions applied only on approval)"
HYGIENE_PROBES=(
  ".claude/settings.local.json"
  ".opencode/package.json"
  ".opencode/package-lock.json"
  ".opencode/node_modules"
)
HAPPLIED=()
for p in ${HYGIENE_PROBES[@]+"${HYGIENE_PROBES[@]}"}; do
  [ -e "$p" ] || continue
  if git check-ignore -q -- "$p" 2>/dev/null; then continue; fi    # already ignored somewhere
  if [ "$DRY_RUN" -eq 1 ]; then ev H warn "untracked runtime file present, not ignored anywhere: $p (suggest .gitignore)"; continue; fi
  if [ "$YES" -eq 1 ]; then HAPPLIED+=("$p"); ev H info "gitignore entry added (via --yes): $p"
  elif [ -t 0 ] && [ "$DRY_RUN" -eq 0 ]; then
    printf '   Add .gitignore entry for currently-untracked %s? [y/N] ' "$p"
    read -r ans; case "${ans:-N}" in y|Y) HAPPLIED+=("$p"); ev H info "gitignore entry added (approved): $p";; *) ev H warn "skipped gitignore suggestion: $p" ;; esac
  else ev H warn "untracked runtime file present, not ignored anywhere: $p (suggest adding to .gitignore)"
  fi
done
if [ ${#HAPPLIED[@]} -gt 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  touch .gitignore
  if ! grep -qF "# BEGIN agent-init hygiene" .gitignore; then
    { echo ""; echo "# BEGIN agent-init hygiene (managed block — edits preserved on re-runs)"; for p in ${HAPPLIED[@]+"${HAPPLIED[@]}"}; do echo "$p/"; echo "$p"; done
      echo "# END agent-init hygiene"; } >> .gitignore
    info "   ↳ appended marker-guarded hygiene block to .gitignore"
  fi
fi

# ================================================================ phase 7 : global (user-level) scan — report + per-item
GLOBAL_DECISIONS=()
if [ "$NO_GLOBAL" -eq 0 ]; then
  info ""
  info "Phase 7: user-level (~) standardization candidates — linkable real dirs only"
  GHOME="${AGENT_INIT_HOME:-$HOME}"
  # candidates: harness | source dir (abs, in $GHOME) | target rel-to-home category
  GCANDS=()
  [ -d "$GHOME/.claude/rules" ]    && GCANDS+=("claude|$GHOME/.claude/rules|rules")
  [ -d "$GHOME/.claude/skills" ]   && GCANDS+=("claude|$GHOME/.claude/skills|skills")
  report_only_skip() { ev G warn "excluded: $1 — $2"; }
  [ -d "${HERMES_HOME:-$GHOME/.hermes}/skills" ] && report_only_skip "\$HERMES_HOME/skills" "category-style tree managed by hermes (not portable plain skills)"
  [ -d "$GHOME/.cursor/rules" ]    && report_only_skip "~/.cursor/rules" ".mdc format is cursor-specific; convert before linking"
  [ -d "$GHOME/.cursor/agents" ]   && report_only_skip "~/.cursor/agents" "no verified cross-harness project convention yet"
  if [ ${#GCANDS[@]} -eq 0 ]; then info "   no linkable global candidates found."; else
    for c in ${GCANDS[@]+"${GCANDS[@]}"}; do
      IFS='|' read -r gh gsrc gcat <<<"$c"
      fmt_ok=1
      while IFS= read -r -d '' g; do
        case "$g" in *.md) : ;; *) fmt_ok=0; ev G warn "skipped $gsrc: non-plain-md file found ($g)"; break;; esac
      done < <(find "$gsrc" -maxdepth 2 -type f -print0 2>/dev/null | head -z -n 50)
      [ "$fmt_ok" = 0 ] && continue
      gdest="$GHOME/.agents/$gcat"
      if [ "$DRY_RUN" -eq 1 ]; then GDECISION="report-only (dry-run)"
      elif [ "$YES" -eq 1 ]; then GDECISION=approved
      elif [ -t 0 ]; then printf '   Link %s -> ~/.agents/%s ? [y/N] ' "$gsrc" "$gcat"; read -r ans; case "${ans:-N}" in y|Y) GDECISION=approved;; *) GDECISION=declined ;; esac
      else GDECISION="report-only (non-interactive)"; fi
      printf '   %-34s -> ~/.agents/%s  [%s]\n' "$gsrc" "$gcat" "$GDECISION"
      case "$GDECISION" in
          approved)
            ensure_backup
            mkdir -p "$gdest"
            merged=0; left=0
           while IFS= read -r -d '' g; do
             rel="${g#"$gsrc"/}"
             if [ -e "$gdest/$rel" ]; then
               if [ "$(hash_f "$g")" = "$(hash_f "$gdest/$rel")" ]; then merged=$((merged+1)); else left=$((left+1)); fi
               continue                                       # never clobber existing global content (X1: divergence stays human)
             fi
             mkdir -p "$(dirname "$gdest/$rel")"; cp --reflink=auto -p -- "$g" "$STAGE/y" 2>/dev/null || cp -p -- "$g" "$STAGE/y"
             mv -T -- "$STAGE/y" "$gdest/$rel"; merged=$((merged+1))
           done < <(find "$gsrc" -type f -print0 | sort -z)
           if [ "$left" -eq 0 ] && [ ! -L "$gsrc" ]; then     # fully consolidated → link-port the source dir
             GBACK="$GHOME/.agent-init-backup/$TS"; mkdir -p "$GBACK"
             ( cd "$GHOME" && mv -- "${gsrc#"$GHOME"/}" "$GBACK/${gsrc#"$GHOME"/}.__real__" \
               && ln -srn -- ".agents/$gcat" "${gsrc#"$GHOME"/}" )
             ev G info "global link-port: $gsrc -> ~/.agents/$gcat (original real dir preserved in ~/.agent-init-backup/$TS/)"
           else
             ev G warn "divergence at global scope for $gsrc ($left entries differ from existing canonical) — kept as real dir, reconciliation left to human (D7)"
           fi ;;
       esac
    done
  fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo ""
  info "--dry-run: matrix fully evaluated above; zero mutations performed."
  write_report; exit 0
fi

# ================================================================ phase 8 : summary
info ""
echo "==================== SUMMARY ===================="
for h in ${HNAMES[@]+"${HNAMES[@]}"}; do printf '   %-10s installed=%s decision=%s\n' "$h" "${INSTALLED[$h]}" "${DECISIONS[$h]:-n/a}"; done
info "   backup dir : $BACKUP_DIR"
  info "   report     : $REPORT_FILE (audit sidecar; git-ignore if not for version control)"
write_report
echo ""
[ "${BLOCK_COUNT}" -gt 0 ] && info "NOTE: blocked conflict(s) remain — see report for manual resolution." || true
exit 0
