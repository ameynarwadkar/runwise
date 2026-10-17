"""
Unit and Integration Tests for the CI/CD Evaluation Gate.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from runwise.evals.gate import (
    GateThresholds,
    RunMetrics,
    compare_eval_runs,
    compute_p95,
    load_metrics_from_run,
)


@pytest.fixture
def baseline_metrics() -> RunMetrics:
    return RunMetrics(
        total_tasks=15,
        total_trials=45,
        overall_pass_rate=1.0,
        p95_latency_ms=1200.0,
        mean_latency_ms=850.0,
        avg_tokens=450.0,
        category_pass_rates={"cancellation": 1.0, "refund": 1.0},
    )


def test_compute_p95_accurate():
    vals = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0]
    p95 = compute_p95(vals)
    assert p95 == 1000.0

    vals_empty = []
    assert compute_p95(vals_empty) == 0.0


def test_gate_passes_when_metrics_identical(baseline_metrics: RunMetrics):
    candidate = baseline_metrics.model_copy()
    res = compare_eval_runs(candidate, baseline_metrics)
    assert res.passed is True
    assert len(res.violations) == 0
    assert "✅ PASS" in res.markdown_report


def test_gate_passes_when_metrics_improve(baseline_metrics: RunMetrics):
    candidate = baseline_metrics.model_copy(
        update={
            "overall_pass_rate": 1.0,
            "p95_latency_ms": 1050.0,  # faster
            "avg_tokens": 400.0,       # cheaper
        }
    )
    res = compare_eval_runs(candidate, baseline_metrics)
    assert res.passed is True
    assert len(res.violations) == 0


def test_gate_blocks_on_pass_rate_drop(baseline_metrics: RunMetrics):
    # Baseline: 100%, candidate: 97% (drop of 3% > 2% max threshold)
    candidate = baseline_metrics.model_copy(update={"overall_pass_rate": 0.97})
    res = compare_eval_runs(candidate, baseline_metrics)
    assert res.passed is False
    assert len(res.violations) == 1
    assert "Pass rate dropped by 3.00%" in res.violations[0]
    assert "❌ BLOCKED" in res.markdown_report


def test_gate_blocks_on_latency_regression(baseline_metrics: RunMetrics):
    # Baseline p95: 1200ms. +20% -> 1440ms (> 15% threshold)
    candidate = baseline_metrics.model_copy(update={"p95_latency_ms": 1450.0})
    res = compare_eval_runs(candidate, baseline_metrics)
    assert res.passed is False
    assert any("p95 latency increased" in v for v in res.violations)
    assert "❌ BLOCKED" in res.markdown_report


def test_gate_blocks_on_token_cost_explosion(baseline_metrics: RunMetrics):
    # Baseline: 450 tokens. +20% -> 540 tokens (> 15% threshold)
    candidate = baseline_metrics.model_copy(update={"avg_tokens": 550.0})
    res = compare_eval_runs(candidate, baseline_metrics)
    assert res.passed is False
    assert any("Average token usage increased" in v for v in res.violations)


def test_load_metrics_from_run_directory(tmp_path: Path):
    summary_data = {
        "total_tasks": 10,
        "total_trials": 10,
        "overall_success_rate": 0.95,
        "category_success_rates": {"refund": 1.0},
    }
    with open(tmp_path / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_data, f)

    trajectories = [
        {"usage": {"latency_ms": 800.0, "total_tokens": 300}},
        {"usage": {"latency_ms": 1200.0, "total_tokens": 500}},
    ]
    with open(tmp_path / "trajectories.jsonl", "w", encoding="utf-8") as f:
        for t in trajectories:
            f.write(json.dumps(t) + "\n")

    metrics = load_metrics_from_run(tmp_path)
    assert metrics.total_tasks == 10
    assert metrics.overall_pass_rate == 0.95
    assert metrics.avg_tokens == 400.0
    assert metrics.mean_latency_ms == 1000.0
    assert metrics.p95_latency_ms == 1200.0
