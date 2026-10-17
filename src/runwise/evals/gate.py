"""
Evaluation Gate Engine & Regression Comparator.

Automates PR regression gating against baseline metrics according to llmops.md:
1. Accuracy threshold: Blocks PR if pass rate drops by more than `max_accuracy_drop` (default 2%).
2. Latency threshold: Blocks PR if p95 latency increases by more than `max_latency_p95_increase_ratio` (default 15%).
3. Token/Cost threshold: Blocks PR if average tokens per trial increases by more than `max_token_increase_ratio` (default 15%).
4. Markdown Report Generator: Formats a GitHub Step Summary / PR Comment table.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
from typing import Any
from pydantic import BaseModel, Field


class GateThresholds(BaseModel):
    """Configurable regression thresholds for the evaluation gate."""
    max_accuracy_drop: float = 0.02           # Max allowable drop in pass rate (e.g. 0.02 = 2.0%)
    max_latency_p95_increase_ratio: float = 0.15  # Max allowable ratio increase in p95 latency (15%)
    max_token_increase_ratio: float = 0.15        # Max allowable ratio increase in avg tokens (15%)


class RunMetrics(BaseModel):
    """Extracted evaluation metrics from a benchmark run."""
    total_tasks: int
    total_trials: int
    overall_pass_rate: float
    p95_latency_ms: float
    mean_latency_ms: float
    avg_tokens: float
    category_pass_rates: dict[str, float] = Field(default_factory=dict)


class GateEvaluationResult(BaseModel):
    """Result of comparing candidate metrics against baseline."""
    passed: bool
    violations: list[str] = Field(default_factory=list)
    markdown_report: str = ""
    candidate: RunMetrics
    baseline: RunMetrics


def compute_p95(values: list[float]) -> float:
    """Computes the 95th percentile using nearest-rank interpolation."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(math.ceil(0.95 * len(sorted_vals))) - 1
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return float(sorted_vals[idx])


def load_metrics_from_run(run_path: Path | str) -> RunMetrics:
    """
    Loads benchmark run metrics from a run directory or summary.json file.
    Also parses trajectories.jsonl if present to extract granular p95 latency and token metrics.
    """
    path = Path(run_path)
    if path.is_dir():
        summary_file = path / "summary.json"
        traj_file = path / "trajectories.jsonl"
    else:
        summary_file = path
        traj_file = path.parent / "trajectories.jsonl"

    if not summary_file.exists():
        raise FileNotFoundError(f"Evaluation summary file not found: {summary_file}")

    with open(summary_file, "r", encoding="utf-8") as f:
        summary_data = json.load(f)

    total_tasks = summary_data.get("total_tasks", 0)
    total_trials = summary_data.get("total_trials", 0)
    overall_pass_rate = summary_data.get("overall_success_rate", 0.0)
    category_pass_rates = summary_data.get("category_success_rates", {})

    latencies: list[float] = []
    tokens: list[int] = []

    # If trajectories.jsonl exists, compute true p95 latency and avg tokens from individual trials
    if traj_file.exists():
        with open(traj_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    usage = record.get("usage") or {}
                    lat = usage.get("latency_ms", 0.0)
                    tok = usage.get("total_tokens", 0)
                    if lat > 0:
                        latencies.append(float(lat))
                    if tok > 0:
                        tokens.append(int(tok))
                except Exception:
                    continue

    p95_lat = compute_p95(latencies) if latencies else float(summary_data.get("p95_latency_ms", 0.0))
    mean_lat = (sum(latencies) / len(latencies)) if latencies else float(summary_data.get("mean_latency_ms", 0.0))
    avg_tok = (sum(tokens) / len(tokens)) if tokens else float(summary_data.get("avg_tokens", 0.0))

    return RunMetrics(
        total_tasks=total_tasks,
        total_trials=total_trials,
        overall_pass_rate=overall_pass_rate,
        p95_latency_ms=p95_lat,
        mean_latency_ms=mean_lat,
        avg_tokens=avg_tok,
        category_pass_rates=category_pass_rates,
    )


def compare_eval_runs(
    candidate: RunMetrics,
    baseline: RunMetrics,
    thresholds: GateThresholds | None = None,
) -> GateEvaluationResult:
    """
    Evaluates whether the candidate run passes the evaluation gate relative to baseline.
    """
    if thresholds is None:
        thresholds = GateThresholds()

    violations: list[str] = []

    # 1. Accuracy Check
    acc_diff = candidate.overall_pass_rate - baseline.overall_pass_rate
    acc_drop = baseline.overall_pass_rate - candidate.overall_pass_rate
    acc_passed = acc_drop <= thresholds.max_accuracy_drop
    if not acc_passed:
        violations.append(
            f"Pass rate dropped by {acc_drop * 100:.2f}% "
            f"(from {baseline.overall_pass_rate * 100:.1f}% to {candidate.overall_pass_rate * 100:.1f}%), "
            f"exceeding max allowable drop of {thresholds.max_accuracy_drop * 100:.1f}%."
        )

    # 2. p95 Latency Check
    lat_passed = True
    lat_diff_pct = 0.0
    if baseline.p95_latency_ms > 0:
        lat_diff = candidate.p95_latency_ms - baseline.p95_latency_ms
        lat_diff_pct = (lat_diff / baseline.p95_latency_ms) * 100
        if lat_diff / baseline.p95_latency_ms > thresholds.max_latency_p95_increase_ratio:
            lat_passed = False
            violations.append(
                f"p95 latency increased by {lat_diff_pct:+.1f}% "
                f"({baseline.p95_latency_ms:.0f}ms -> {candidate.p95_latency_ms:.0f}ms), "
                f"exceeding max threshold of +{thresholds.max_latency_p95_increase_ratio * 100:.1f}%."
            )

    # 3. Token / Cost Check
    tok_passed = True
    tok_diff_pct = 0.0
    if baseline.avg_tokens > 0:
        tok_diff = candidate.avg_tokens - baseline.avg_tokens
        tok_diff_pct = (tok_diff / baseline.avg_tokens) * 100
        if tok_diff / baseline.avg_tokens > thresholds.max_token_increase_ratio:
            tok_passed = False
            violations.append(
                f"Average token usage increased by {tok_diff_pct:+.1f}% "
                f"({baseline.avg_tokens:.1f} -> {candidate.avg_tokens:.1f}), "
                f"exceeding max threshold of +{thresholds.max_token_increase_ratio * 100:.1f}%."
            )

    overall_passed = len(violations) == 0

    # Build Markdown Comparison Table
    status_icon = "✅ PASS" if overall_passed else "❌ BLOCKED"
    acc_icon = "✅ PASS" if acc_passed else "❌ FAIL"
    lat_icon = "✅ PASS" if lat_passed else "❌ FAIL"
    tok_icon = "✅ PASS" if tok_passed else "❌ FAIL"

    report_lines = [
        f"## 🛡️ Evaluation Gate Summary: {status_icon}",
        "",
        "| Metric | Baseline (`main`) | Candidate (PR) | Delta | Gate Policy | Status |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
        f"| **Pass Rate** | {baseline.overall_pass_rate * 100:.1f}% | {candidate.overall_pass_rate * 100:.1f}% | {acc_diff * 100:+.1f}% | Max Drop $\\le$ {thresholds.max_accuracy_drop * 100:.1f}% | {acc_icon} |",
        f"| **p95 Latency** | {baseline.p95_latency_ms:.0f} ms | {candidate.p95_latency_ms:.0f} ms | {lat_diff_pct:+.1f}% | Max Regress $\\le$ +{thresholds.max_latency_p95_increase_ratio * 100:.1f}% | {lat_icon} |",
        f"| **Avg Tokens** | {baseline.avg_tokens:.1f} | {candidate.avg_tokens:.1f} | {tok_diff_pct:+.1f}% | Max Regress $\\le$ +{thresholds.max_token_increase_ratio * 100:.1f}% | {tok_icon} |",
        f"| **Evaluated Tasks** | {baseline.total_tasks} | {candidate.total_tasks} | {candidate.total_tasks - baseline.total_tasks:+d} | Sample consistency | ℹ️ |",
        "",
    ]

    if violations:
        report_lines.append("### ⚠️ Regression Policy Violations:")
        for v in violations:
            report_lines.append(f"- ❌ {v}")
        report_lines.append("")
    else:
        report_lines.append("✨ All benchmark metrics satisfied production SLOs. Safe to merge!")
        report_lines.append("")

    return GateEvaluationResult(
        passed=overall_passed,
        violations=violations,
        markdown_report="\n".join(report_lines),
        candidate=candidate,
        baseline=baseline,
    )


def main() -> None:
    """CLI Entrypoint for GitHub Actions Evaluation Gate."""
    parser = argparse.ArgumentParser(description="Runwise CI/CD Evaluation Gate")
    parser.add_argument("--candidate", type=str, required=True, help="Path to candidate summary.json or run dir")
    parser.add_argument("--baseline", type=str, required=True, help="Path to baseline summary.json or run dir")
    parser.add_argument("--github-summary", type=str, default=None, help="File path to write GITHUB_STEP_SUMMARY markdown")
    parser.add_argument("--max-acc-drop", type=float, default=0.02, help="Max allowable pass rate drop (default 0.02)")
    parser.add_argument("--max-lat-regress", type=float, default=0.15, help="Max allowable p95 latency ratio increase (default 0.15)")
    parser.add_argument("--max-tok-regress", type=float, default=0.15, help="Max allowable token ratio increase (default 0.15)")

    args = parser.parse_args()

    thresholds = GateThresholds(
        max_accuracy_drop=args.max_acc_drop,
        max_latency_p95_increase_ratio=args.max_lat_regress,
        max_token_increase_ratio=args.max_tok_regress,
    )

    try:
        candidate_metrics = load_metrics_from_run(args.candidate)
        baseline_metrics = load_metrics_from_run(args.baseline)
    except Exception as e:
        print(f"❌ Error loading benchmark run metrics: {e}", file=sys.stderr)
        sys.exit(2)

    result = compare_eval_runs(candidate_metrics, baseline_metrics, thresholds)

    # Print to stdout for CI logs
    print(result.markdown_report)

    # Write to GITHUB_STEP_SUMMARY if requested or present in env
    step_summary_file = args.github_summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_file:
        try:
            with open(step_summary_file, "a", encoding="utf-8") as f:
                f.write(result.markdown_report + "\n")
        except Exception as e:
            print(f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)

    if not result.passed:
        print(f"🛑 Evaluation Gate FAILED: {len(result.violations)} policy violation(s).", file=sys.stderr)
        sys.exit(1)

    print("🚀 Evaluation Gate PASSED!")
    sys.exit(0)


if __name__ == "__main__":
    main()
