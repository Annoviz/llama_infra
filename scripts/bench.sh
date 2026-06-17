#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# bench.sh — Model benchmark runner with optional regression comparison.
#
# Usage:
#   scripts/bench.sh <model_flavor> --output-dir <dir> [extra args ...]
#
# Arguments:
#   model_flavor     One of: planner, coder, fast-coder (custom names, not Ollama IDs)
#   --output-dir DIR Directory for results.json (created if needed)
#   extra args       Passed through to perf_test.sh
#
# Regression: If <dir>/reg-results.json exists, compares current results against it.
#             If not found, saves the last-iteration results as reg-results.json
#             so future runs have a reference to compare against.
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REGRESSION_SCRIPT="$SCRIPT_DIR/model_regression.py"

# ── Model flavor → Ollama model ID mapping ───────────────────────────────────
declare -A MODEL_MAP=(
    [planner]="planner"
    [coder]="coder"
    [fast-coder]="fast-coder"
)

# ── Helpers ──────────────────────────────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }

run_perf_test() {
    local output_dir="$1"; shift

    mkdir -p "$output_dir"

    echo "Running performance test → $output_dir ..." >&2
    bash "$SCRIPT_DIR/perf_test.sh" \
        --save-baseline \
        --output-dir "$output_dir" \
        "$@"

    return $?
}

# Compare current results against reg-results.json in output_dir.
run_regression() {
    local output_dir="$1"; shift

    # Separate extra result files from perf_test.py flags (start with --).
    local extra_results=()
    local reg_args=()
    for arg in "$@"; do
        case "$arg" in
            --*) reg_args+=("$arg") ;;
            *)   extra_results+=("$arg") ;;
        esac
    done

    local reg_file="$output_dir/reg-results.json"

    if [ ! -f "$reg_file" ]; then
        # No reference exists — save last-measured iteration as the new baseline.
        echo "No $reg_file found — saving current results as regression baseline." >&2
        # Prefer baseline.json (last measured iteration per combo, warmup skipped),
        # fall back to full results.json for backward compat.
        if [ -f "$output_dir/baseline.json" ]; then
            cp "$output_dir/baseline.json" "$reg_file"
        else
            cp "$output_dir/results.json" "$reg_file"
        fi
        return 0
    fi

    # Reference exists — run comparison.
    local all_current=("$output_dir/results.json")
    for f in "${extra_results[@]}"; do
        if [ -f "$f" ]; then
            all_current+=("$f")
        else
            echo "Warning: $f not found, skipping." >&2
        fi
    done

    echo "Comparing against $reg_file ..." >&2
    python3 "$REGRESSION_SCRIPT" \
        --reference "$reg_file" \
        "${all_current[@]}" \
        --output-dir "$output_dir" \
        "${reg_args[@]+"${reg_args[@]}"}"
}

# ── Main ─────────────────────────────────────────────────────────────────────

[ $# -lt 1 ] && {
    echo "Usage: scripts/bench.sh <model_flavor> --output-dir <dir> [extra args ...]" >&2
    echo "" >&2
    echo "Model flavors:" >&2
    for flavor in "${!MODEL_MAP[@]}"; do
        printf "  %-14s → %s\n" "$flavor" "${MODEL_MAP[$flavor]}" >&2
    done
    exit 1
}

model_flavor="$1"
shift

model_id="${MODEL_MAP[$model_flavor]:-}"
[ -z "$model_id" ] && die "Unknown model flavor '$model_flavor'. Available: ${!MODEL_MAP[*]}"

# Parse --output-dir from remaining args.
output_dir=""
extra_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        --output-dir) output_dir="$2"; shift 2 ;;
        *) extra_args+=("$1"); shift ;;
    esac
done

[ -z "$output_dir" ] && die "--output-dir is required"

# Default to model flavor unless explicitly overridden.
has_model_flag=false
for arg in "${extra_args[@]+"${extra_args[@]}"}"; do
    case "$arg" in
        --model) has_model_flag=true; break ;;
    esac
done
if [ "$has_model_flag" = false ]; then
    extra_args=(--model "$model_id" "${extra_args[@]+"${extra_args[@]}"}")
fi

# Run perf_test.
run_perf_test "$output_dir" "${extra_args[@]}" || exit $?

# Regression comparison (or baseline save).
run_regression "$output_dir" "${extra_args[@]+"${extra_args[@]}"}"
