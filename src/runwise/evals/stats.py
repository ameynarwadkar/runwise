"""
Statistical Reliability and Evaluation Metrics Engine.

Implements rigorous evaluation metrics from tau-bench and evals.md:
1. pass^k (Consensus / Deterministic reliability: probability all k trials succeed)
2. pass@k (Exploration / Best-of-k: probability at least one trial succeeds)
3. Flip Rate (Diagnostic noise floor measuring run-to-run instability)
4. Granular breakdowns by operational category and task difficulty.
"""

from __future__ import annotations

import math
from typing import Any
from pydantic import BaseModel, Field

from runwise.evals.models import TrialOutcome


class TrialRecord(BaseModel):
    """Execution record for an individual trial."""
    task_id: str
    trial_id: str
    category: str
    difficulty: str
    split: str
    outcome: TrialOutcome
    latency_ms: float = 0.0
    total_tokens: int = 0


class TaskSummary(BaseModel):
    """Aggregated multi-trial statistics for a single task."""
    task_id: str
    category: str
    difficulty: str
    split: str
    total_trials: int
    successful_trials: int
    pass_rate: float
    pass_hat_k: dict[int, float] = Field(default_factory=dict)
    pass_at_k: dict[int, float] = Field(default_factory=dict)


class EvaluationSummary(BaseModel):
    """Comprehensive benchmark results report."""
    total_tasks: int
    total_trials: int
    overall_success_rate: float
    pass_hat_k: dict[int, float]
    pass_at_k: dict[int, float]
    category_success_rates: dict[str, float]
    difficulty_success_rates: dict[str, float]
    split_success_rates: dict[str, float]
    task_summaries: list[TaskSummary]


def calculate_pass_hat_k(n: int, c: int, k: int) -> float:
    """
    Computes pass^k (probability that all k trials succeed).
    Formula: comb(c, k) / comb(n, k)
    Returns 0.0 if c < k or n < k.
    """
    if n < k or c < k:
        return 0.0
    try:
        return math.comb(c, k) / math.comb(n, k)
    except ZeroDivisionError:
        return 0.0


def calculate_pass_at_k(n: int, c: int, k: int) -> float:
    """
    Computes pass@k (probability that at least one trial succeeds out of k).
    Formula: 1 - comb(n - c, k) / comb(n, k)
    Returns 0.0 if c == 0; returns 1.0 if c >= n - k + 1.
    """
    if c == 0 or n < k:
        return 0.0
    if n - c < k:
        return 1.0
    try:
        return 1.0 - (math.comb(n - c, k) / math.comb(n, k))
    except ZeroDivisionError:
        return 0.0


def compute_flip_rate(
    run_1_records: list[TrialRecord],
    run_2_records: list[TrialRecord],
) -> float:
    """
    Computes the empirical Flip Rate between two identical evaluation runs.
    Measures the proportion of (task_id, trial_index) pairs whose outcome flipped.
    """
    if not run_1_records or not run_2_records:
        return 0.0

    # Index run 1 by (task_id, trial_id)
    r1_map = {(r.task_id, r.trial_id): (r.outcome == TrialOutcome.PASS) for r in run_1_records}
    r2_map = {(r.task_id, r.trial_id): (r.outcome == TrialOutcome.PASS) for r in run_2_records}

    common_keys = set(r1_map.keys()) & set(r2_map.keys())
    if not common_keys:
        return 0.0

    flips = sum(1 for k in common_keys if r1_map[k] != r2_map[k])
    return flips / len(common_keys)


def compute_evaluation_summary(
    records: list[TrialRecord],
    k_values: list[int] | None = None,
) -> EvaluationSummary:
    """
    Aggregates a flat list of trial records into a full EvaluationSummary report.
    """
    if k_values is None:
        k_values = [1, 2, 4]

    # Group records by task_id
    tasks_map: dict[str, list[TrialRecord]] = {}
    for r in records:
        tasks_map.setdefault(r.task_id, []).append(r)

    task_summaries: list[TaskSummary] = []
    for task_id, task_records in tasks_map.items():
        sample = task_records[0]
        n = len(task_records)
        c = sum(1 for r in task_records if r.outcome == TrialOutcome.PASS)
        rate = c / n if n > 0 else 0.0

        p_hat = {k: calculate_pass_hat_k(n, c, k) for k in k_values if k <= n}
        p_at = {k: calculate_pass_at_k(n, c, k) for k in k_values if k <= n}

        task_summaries.append(
            TaskSummary(
                task_id=task_id,
                category=sample.category,
                difficulty=sample.difficulty,
                split=sample.split,
                total_trials=n,
                successful_trials=c,
                pass_rate=round(rate, 4),
                pass_hat_k={k: round(v, 4) for k, v in p_hat.items()},
                pass_at_k={k: round(v, 4) for k, v in p_at.items()},
            )
        )

    total_tasks = len(task_summaries)
    total_trials = len(records)
    total_passed_trials = sum(1 for r in records if r.outcome == TrialOutcome.PASS)
    overall_rate = total_passed_trials / total_trials if total_trials > 0 else 0.0

    # Macro averages across tasks for pass^k and pass@k
    agg_pass_hat_k: dict[int, float] = {}
    agg_pass_at_k: dict[int, float] = {}

    for k in k_values:
        valid_hat = [ts.pass_hat_k[k] for ts in task_summaries if k in ts.pass_hat_k]
        valid_at = [ts.pass_at_k[k] for ts in task_summaries if k in ts.pass_at_k]
        if valid_hat:
            agg_pass_hat_k[k] = round(sum(valid_hat) / len(valid_hat), 4)
        if valid_at:
            agg_pass_at_k[k] = round(sum(valid_at) / len(valid_at), 4)

    # Category breakdowns
    categories = sorted(list(set(r.category for r in records)))
    cat_rates: dict[str, float] = {}
    for cat in categories:
        cat_recs = [r for r in records if r.category == cat]
        cat_pass = sum(1 for r in cat_recs if r.outcome == TrialOutcome.PASS)
        cat_rates[cat] = round(cat_pass / len(cat_recs), 4) if cat_recs else 0.0

    # Difficulty breakdowns
    difficulties = sorted(list(set(r.difficulty for r in records)))
    diff_rates: dict[str, float] = {}
    for diff in difficulties:
        diff_recs = [r for r in records if r.difficulty == diff]
        diff_pass = sum(1 for r in diff_recs if r.outcome == TrialOutcome.PASS)
        diff_rates[diff] = round(diff_pass / len(diff_recs), 4) if diff_recs else 0.0

    # Split breakdowns
    splits = sorted(list(set(r.split for r in records)))
    split_rates: dict[str, float] = {}
    for sp in splits:
        sp_recs = [r for r in records if r.split == sp]
        sp_pass = sum(1 for r in sp_recs if r.outcome == TrialOutcome.PASS)
        split_rates[sp] = round(sp_pass / len(sp_recs), 4) if sp_recs else 0.0

    return EvaluationSummary(
        total_tasks=total_tasks,
        total_trials=total_trials,
        overall_success_rate=round(overall_rate, 4),
        pass_hat_k=agg_pass_hat_k,
        pass_at_k=agg_pass_at_k,
        category_success_rates=cat_rates,
        difficulty_success_rates=diff_rates,
        split_success_rates=split_rates,
        task_summaries=task_summaries,
    )
