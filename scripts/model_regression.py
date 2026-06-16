"""
model_regression.py — Compare benchmark runs against a reference results file.

Loads reference results from a results.json (or --reference flag) and compares
each matched run by (model, prompt).  Two kinds of comparison are performed:

1. **Performance regression** — metric deltas between current run(s) and the
   reference aggregates (mean tokens/s, TTFT, duration, etc.).
2. **Output consistency** — whether the text output is identical across all
   iterations within a combo, and how similar it is to the reference output
   (first iteration of the reference combo).

Usage:
  python3 scripts/model_regression.py --reference ref_results.json [current_results.json ...]
  python3 scripts/model_regression.py --reference ref_results.json --output-dir ./regression

Options:
  --reference FILE      Reference results.json to compare against (required)
  --output-dir DIR      Directory for regression report (auto-generated run_id)
  --base-url URL        Ollama base URL shown in the header
  --warn-threshold PCT  Warn if metric regresses by this % or more (default: 5)
  --critical-threshold PCT  Critical if metric regresses by this % or more (default: 10)

Exit codes:
  0  No regressions detected
  1  One or more critical regressions found
  2  One or more warnings (but no criticals)
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


# Metrics to compare numerically.  Higher is better (↓ = regression if current < ref).
NUMERIC_METRICS_HIGHER_BETTER = ["tokens_per_sec", "avg_tokens_per_sec"]

# Metrics to compare numerically.  Lower is better (↑ = regression if current > ref).
NUMERIC_METRICS_LOWER_BETTER = [
    "first_token_ms", "avg_first_token_ms",
    "total_duration_s", "avg_total_duration_s",
]


@dataclass
class RegressionFinding:
    model: str
    prompt_label: str
    metric_name: str
    ref_value: float
    current_value: float
    delta_pct: float  # positive = regression, negative = improvement
    direction: str   # "higher_better" or "lower_better"


@dataclass
class ConsistencyFinding:
    model: str
    prompt_label: str
    finding: str     # human-readable description
    severity: str    # "ok", "warn", "critical"


def load_results(path: str) -> dict:
    """Load a results.json file and return its parsed structure."""
    with open(path, "r") as f:
        data = json.load(f)

    # Support both flat list format (old perf_test output) and new wrapped format.
    if isinstance(data, list):
        if len(data) > 0 and "run_id" in data[0]:
            return {"results": data}
        return {"results": data}

    # New wrapped format: has run_id, timestamp, results[]
    return data


def _compute_aggregates_from_records(combo_records: List[Dict[str, Any]]) -> Optional[dict]:
    """Compute aggregates from a list of per-iteration result records."""
    if not combo_records:
        return None

    def _extract(metric_name: str) -> List[float]:
        vals = [r["metrics"].get(metric_name, 0.0) for r in combo_records]
        return [v for v in vals if v is not None and v > 0]

    first_token_ms_vals = _extract("first_token_ms")
    total_duration_s_vals = _extract("total_duration_s")
    tokens_per_sec_vals = _extract("tokens_per_sec")
    input_tokens_vals = _extract("input_tokens")
    output_tokens_vals = _extract("output_tokens")

    if not first_token_ms_vals:
        return None

    return {
        "avg_first_token_ms": sum(first_token_ms_vals) / len(first_token_ms_vals),
        "min_first_token_ms": min(first_token_ms_vals),
        "max_first_token_ms": max(first_token_ms_vals),
        "avg_total_duration_s": sum(total_duration_s_vals) / len(total_duration_s_vals) if total_duration_s_vals else 0,
        "min_total_duration_s": min(total_duration_s_vals) if total_duration_s_vals else 0,
        "max_total_duration_s": max(total_duration_s_vals) if total_duration_s_vals else 0,
        "avg_tokens_per_sec": sum(tokens_per_sec_vals) / len(tokens_per_sec_vals) if tokens_per_sec_vals else 0,
        "min_tokens_per_sec": min(tokens_per_sec_vals) if tokens_per_sec_vals else 0,
        "max_tokens_per_sec": max(tokens_per_sec_vals) if tokens_per_sec_vals else 0,
    }


def get_aggregates_for_combo(results: List[Dict[str, Any]], model: str, prompt_label: str) -> Optional[dict]:
    """Compute aggregates for a specific (model, prompt_label) combo from raw metrics."""
    combos = {}
    for rec in results:
        key = (rec.get("model"), rec.get("prompt_label"))
        if key not in combos:
            combos[key] = []
        combos[key].append(rec)

    combo_records = combos.get((model, prompt_label), [])
    return _compute_aggregates_from_records(combo_records)


def get_raw_texts(results: List[Dict[str, Any]], model: str, prompt_label: str) -> List[str]:
    """Get raw text outputs for all iterations of a combo."""
    texts = []
    for rec in results:
        if rec.get("model") == model and rec.get("prompt_label") == prompt_label:
            texts.append(rec.get("raw_text", ""))
    return texts


def pct_change(ref: float, current: float) -> Optional[float]:
    """Calculate percentage change from ref to current.

    Returns None if ref is zero or both are equal.
    Positive = improvement (current > ref), negative = regression.
    """
    if ref == 0:
        return None
    return ((current - ref) / abs(ref)) * 100


def compare_performance(reference_data: dict, current_results: List[Dict[str, Any]],
                        warn_threshold: float, critical_threshold: float) -> List[RegressionFinding]:
    """Compare performance metrics between reference and current runs.

    Returns list of RegressionFinding objects for each metric that regressed.
    """
    ref_results = reference_data.get("results", [])
    findings: List[RegressionFinding] = []

    # Build set of (model, prompt_label) combos in both reference and current
    ref_combos = {}
    for rec in ref_results:
        key = (rec.get("model"), rec.get("prompt_label"))
        if key not in ref_combos:
            ref_combos[key] = []
        ref_combos[key].append(rec)

    current_combos = {}
    for rec in current_results:
        key = (rec.get("model"), rec.get("prompt_label"))
        if key not in current_combos:
            current_combos[key] = []
        current_combos[key].append(rec)

    # Only compare combos that exist in BOTH reference and current
    common_keys = set(ref_combos.keys()) & set(current_combos.keys())

    for (model, prompt_label) in sorted(common_keys):
        ref_agg = get_aggregates_for_combo(ref_results, model, prompt_label)
        curr_agg = get_aggregates_for_combo(current_results, model, prompt_label)

        if not ref_agg or not curr_agg:
            continue

        # Compare all numeric metrics
        all_metrics = set(list(NUMERIC_METRICS_HIGHER_BETTER) + list(NUMERIC_METRICS_LOWER_BETTER))
        for metric in sorted(all_metrics):
            if metric not in ref_agg or metric not in curr_agg:
                continue

            ref_val = ref_agg[metric]
            curr_val = curr_agg[metric]

            if ref_val == 0 and curr_val == 0:
                continue

            change_pct = pct_change(ref_val, curr_val)
            if change_pct is None or change_pct == 0:
                continue

            # Determine direction: positive change_pct means current > ref
            higher_better = metric in NUMERIC_METRICS_HIGHER_BETTER

            # Regression: lower value when higher is better, or vice versa
            is_regression = (higher_better and change_pct < 0) or (not higher_better and change_pct > 0)

            if not is_regression:
                continue

            delta_abs = abs(change_pct)
            severity = "ok"
            if delta_abs >= critical_threshold:
                severity = "critical"
            elif delta_abs >= warn_threshold:
                severity = "warn"

            findings.append(RegressionFinding(
                model=model,
                prompt_label=prompt_label,
                metric_name=metric,
                ref_value=ref_val,
                current_value=curr_val,
                delta_pct=delta_abs,  # always positive = regression magnitude
                direction="higher_better" if higher_better else "lower_better",
            ))

    return findings


def compare_output_consistency(reference_data: dict, current_results: List[Dict[str, Any]]) -> List[ConsistencyFinding]:
    """Compare output consistency within iterations and against reference.

    Checks:
      1. Are all iterations producing identical text? (internal consistency)
      2. Is the first iteration's output similar to the reference's first output? (output drift)

    Returns list of ConsistencyFinding objects.
    """
    ref_results = reference_data.get("results", [])
    findings: List[ConsistencyFinding] = []

    # Group by combo
    def _group(results):
        groups = {}
        for rec in results:
            key = (rec.get("model"), rec.get("prompt_label"))
            if key not in groups:
                groups[key] = []
            groups[key].append(rec)
        return groups

    ref_groups = _group(ref_results)
    current_groups = _group(current_results)

    common_keys = set(ref_groups.keys()) & set(current_groups.keys())

    for (model, prompt_label) in sorted(common_keys):
        ref_texts = [r.get("raw_text", "") for r in ref_groups[(model, prompt_label)]]
        curr_texts = [r.get("raw_text", "") for r in current_groups[(model, prompt_label)]]

        # 1. Internal consistency: are all current iterations identical?
        unique_curr = set(curr_texts)
        if len(unique_curr) > 1:
            findings.append(ConsistencyFinding(
                model=model,
                prompt_label=prompt_label,
                finding=f"Output varies across {len(curr_texts)} iterations ({len(unique_curr)} unique outputs)",
                severity="warn",
            ))

        # 2. Compare first iteration output against reference first output (if both have text)
        ref_first = ref_texts[0] if ref_texts else ""
        curr_first = curr_texts[0] if curr_texts else ""

        if not ref_first and not curr_first:
            continue

        if not ref_first or not curr_first:
            findings.append(ConsistencyFinding(
                model=model,
                prompt_label=prompt_label,
                finding="Output consistency: one run has text, the other is empty",
                severity="critical" if (ref_first != curr_first) else "ok",
            ))
            continue

        # Compute similarity ratio using difflib
        ratio = difflib.SequenceMatcher(None, ref_first, curr_first).ratio()

        if ratio < 0.5:
            severity = "critical"
        elif ratio < 0.8:
            severity = "warn"
        else:
            severity = "ok"

        findings.append(ConsistencyFinding(
            model=model,
            prompt_label=prompt_label,
            finding=f"Output similarity: {ratio:.1%} match vs reference (first iteration)",
            severity=severity,
        ))

    return findings


def format_delta(delta_pct: float, direction: str) -> str:
    """Format a delta percentage with direction indicator."""
    arrow = "↓" if direction == "higher_better" else "↑"  # regression arrow
    sign = "-" if direction == "higher_better" else "+"   # numerical sign for regression
    return f"{arrow}{sign}{delta_pct:.1f}%"


def print_report(performance_findings: List[RegressionFinding],
                 consistency_findings: List[ConsistencyFinding]) -> tuple[int, int]:
    """Print a formatted regression report to stdout.

    Returns (critical_count, warn_count).
    """
    critical_count = 0
    warn_count = 0

    if performance_findings or consistency_findings:
        print("=" * 72)
        print("REGRESSION REPORT")
        print("=" * 72)
        print()

    # Performance regressions grouped by combo
    perf_by_combo: dict[tuple[str, str], List[RegressionFinding]] = {}
    for f in performance_findings:
        key = (f.model, f.prompt_label)
        if key not in perf_by_combo:
            perf_by_combo[key] = []
        perf_by_combo[key].append(f)

    if perf_by_combo:
        print("--- Performance Regressions ---\n")
        for (model, prompt_label) in sorted(perf_by_combo.keys()):
            combo_findings = perf_by_combo[(model, prompt_label)]
            print(f"  {model} — {prompt_label}")

            # Sort by severity: critical first, then warn
            sort_order = {"critical": 0, "warn": 1, "ok": 2}
            combo_findings.sort(key=lambda f: (sort_order.get(f.direction == "higher_better", 0), -abs(f.delta_pct)))

            for finding in sorted(combo_findings, key=lambda f: sort_order[("critical" if abs(f.delta_pct) >= 10 else "warn")]):
                severity = "CRITICAL" if abs(finding.delta_pct) >= 10 else "WARN"
                arrow = "↓" if finding.direction == "higher_better" else "↑"
                sign = "-" if finding.direction == "higher_better" else "+"
                delta_str = f"{sign}{finding.delta_pct:.1f}%"

                print(f"    [{severity}] {finding.metric_name}: {finding.ref_value:.2f} → {finding.current_value:.2f}  ({arrow}{delta_str})")
                if abs(finding.delta_pct) >= 10:
                    critical_count += 1
                else:
                    warn_count += 1

            print()

    # Consistency findings grouped by combo
    cons_by_combo: dict[tuple[str, str], List[ConsistencyFinding]] = {}
    for f in consistency_findings:
        key = (f.model, f.prompt_label)
        if key not in cons_by_combo:
            cons_by_combo[key] = []
        cons_by_combo[key].append(f)

    if cons_by_combo:
        print("--- Output Consistency ---\n")
        for (model, prompt_label) in sorted(cons_by_combo.keys()):
            combo_findings = cons_by_combo[(model, prompt_label)]
            print(f"  {model} — {prompt_label}")

            for finding in combo_findings:
                if finding.severity == "ok":
                    continue

                severity_tag = f"[{finding.severity.upper()}]"
                print(f"    {severity_tag} {finding.finding}")
                if finding.severity == "critical":
                    critical_count += 1
                else:
                    warn_count += 1

            print()

    # Summary
    total_issues = critical_count + warn_count
    if total_issues > 0:
        parts = []
        if critical_count:
            parts.append(f"{critical_count} CRITICAL")
        if warn_count:
            parts.append(f"{warn_count} WARN")
        print(f"Issues found: {', '.join(parts)}")
    else:
        print("No regressions detected. All metrics within thresholds.")

    return critical_count, warn_count


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Compare benchmark runs against a reference results file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python3 scripts/model_regression.py --reference ref_results.json current_results.json
  python3 scripts/model_regression.py --reference ref_results.json --output-dir ./regression
  python3 scripts/model_regression.py --reference ref_results.json run1.json run2.json run3.json""",
    )

    parser.add_argument("--reference", required=True, help="Reference results.json to compare against")
    parser.add_argument("current_files", nargs="*", help="Current result files to compare (reads stdin if none given)")
    parser.add_argument("--output-dir", dest="output_dir", help="Directory for regression report JSON")
    parser.add_argument("--base-url", default="", help="Ollama base URL shown in header")
    parser.add_argument("--warn-threshold", type=float, default=5.0, help="Warn if metric regresses by ≥ this %% (default: 5)")
    parser.add_argument("--critical-threshold", type=float, default=10.0, help="Critical if metric regresses by ≥ this %% (default: 10)")

    return parser


def main(argv=None) -> int:
    """Main entry point."""
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    # Load reference results
    try:
        ref_data = load_results(args.reference)
    except Exception as e:
        print(f"Error loading reference file {args.reference}: {e}", file=sys.stderr)
        return 1

    # Load current result files
    current_files = args.current_files
    if not current_files:
        # Read from stdin
        try:
            data = json.load(sys.stdin)
            current_results = data.get("results", data) if isinstance(data, dict) else data
        except Exception as e:
            print(f"Error reading current results from stdin: {e}", file=sys.stderr)
            return 1
    else:
        all_current: List[Dict[str, Any]] = []
        for path in current_files:
            try:
                data = load_results(path)
                all_current.extend(data.get("results", data))
            except Exception as e:
                print(f"Error loading {path}: {e}", file=sys.stderr)
                return 1
        current_results = all_current

    # Run comparisons
    perf_findings = compare_performance(
        ref_data, current_results,
        warn_threshold=args.warn_threshold,
        critical_threshold=args.critical_threshold,
    )
    cons_findings = compare_output_consistency(ref_data, current_results)

    # Print report
    critical_count, warn_count = print_report(perf_findings, cons_findings)
    print()

    # Write JSON report to output_dir if specified
    if args.output_dir:
        try:
            os.makedirs(args.output_dir, exist_ok=True)

            report = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "reference_file": args.reference,
                "current_files": current_files or ["stdin"],
                "warn_threshold": args.warn_threshold,
                "critical_threshold": args.critical_threshold,
                "performance_regressions": [
                    {
                        "model": f.model,
                        "prompt_label": f.prompt_label,
                        "metric_name": f.metric_name,
                        "ref_value": f.ref_value,
                        "current_value": f.current_value,
                        "delta_pct": round(f.delta_pct, 2),
                        "direction": f.direction,
                    }
                    for f in perf_findings
                ],
                "output_consistency": [
                    {
                        "model": f.model,
                        "prompt_label": f.prompt_label,
                        "finding": f.finding,
                        "severity": f.severity,
                    }
                    for f in cons_findings
                ],
                "summary": {
                    "critical_count": critical_count,
                    "warn_count": warn_count,
                    "total_issues": critical_count + warn_count,
                },
            }

            report_path = os.path.join(args.output_dir, "regression_report.json")
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2)
            print(f"Report written to {report_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing report: {e}", file=sys.stderr)

    # Exit code
    if critical_count > 0:
        return 1
    elif warn_count > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
