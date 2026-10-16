"""
Unit tests for Statistical Reliability Engine (pass^k, pass@k, flip rate).
"""

from runwise.evals.models import TrialOutcome
from runwise.evals.stats import (
    TrialRecord,
    calculate_pass_at_k,
    calculate_pass_hat_k,
    compute_evaluation_summary,
    compute_flip_rate,
)


def test_pass_hat_k_perfect_consensus():
    """Verify pass^k is 1.0 when all n trials pass."""
    assert calculate_pass_hat_k(n=4, c=4, k=1) == 1.0
    assert calculate_pass_hat_k(n=4, c=4, k=4) == 1.0


def test_pass_hat_k_partial_success():
    """Verify pass^k combinatorial calculation on partial success."""
    # n=4, c=3, k=2 -> comb(3, 2) / comb(4, 2) = 3 / 6 = 0.5
    assert calculate_pass_hat_k(n=4, c=3, k=2) == 0.5
    # n=4, c=3, k=4 -> 0.0 because c < k
    assert calculate_pass_hat_k(n=4, c=3, k=4) == 0.0


def test_pass_at_k_exploration():
    """Verify pass@k calculation for best-of-k."""
    # n=4, c=1, k=1 -> 1 - comb(3, 1)/comb(4, 1) = 1 - 3/4 = 0.25
    assert calculate_pass_at_k(n=4, c=1, k=1) == 0.25
    # n=4, c=1, k=4 -> At least one pass in 4 trials = 1.0
    assert calculate_pass_at_k(n=4, c=1, k=4) == 1.0
    # Zero successes
    assert calculate_pass_at_k(n=4, c=0, k=2) == 0.0


def test_flip_rate_identical_runs():
    """Verify flip rate is 0.0 when both runs have identical outcomes."""
    r1 = [
        TrialRecord(task_id="t1", trial_id="tr_1", category="cancellation", difficulty="easy", split="dev", outcome=TrialOutcome.PASS),
        TrialRecord(task_id="t2", trial_id="tr_1", category="refund", difficulty="medium", split="dev", outcome=TrialOutcome.FAIL),
    ]
    r2 = [
        TrialRecord(task_id="t1", trial_id="tr_1", category="cancellation", difficulty="easy", split="dev", outcome=TrialOutcome.PASS),
        TrialRecord(task_id="t2", trial_id="tr_1", category="refund", difficulty="medium", split="dev", outcome=TrialOutcome.FAIL),
    ]
    assert compute_flip_rate(r1, r2) == 0.0


def test_flip_rate_with_outcome_changes():
    """Verify flip rate correctly detects flipped trial outcomes."""
    r1 = [
        TrialRecord(task_id="t1", trial_id="tr_1", category="cancellation", difficulty="easy", split="dev", outcome=TrialOutcome.PASS),
        TrialRecord(task_id="t2", trial_id="tr_1", category="refund", difficulty="medium", split="dev", outcome=TrialOutcome.FAIL),
    ]
    r2 = [
        TrialRecord(task_id="t1", trial_id="tr_1", category="cancellation", difficulty="easy", split="dev", outcome=TrialOutcome.FAIL),  # Flipped!
        TrialRecord(task_id="t2", trial_id="tr_1", category="refund", difficulty="medium", split="dev", outcome=TrialOutcome.FAIL),
    ]
    assert compute_flip_rate(r1, r2) == 0.5


def test_compute_evaluation_summary_breakdowns():
    """Verify complete evaluation summary aggregations by category and difficulty."""
    records = [
        TrialRecord(task_id="t1", trial_id="tr_1", category="cancellation", difficulty="easy", split="dev", outcome=TrialOutcome.PASS),
        TrialRecord(task_id="t1", trial_id="tr_2", category="cancellation", difficulty="easy", split="dev", outcome=TrialOutcome.PASS),
        TrialRecord(task_id="t2", trial_id="tr_1", category="refund", difficulty="hard", split="frozen_holdout", outcome=TrialOutcome.FAIL),
        TrialRecord(task_id="t2", trial_id="tr_2", category="refund", difficulty="hard", split="frozen_holdout", outcome=TrialOutcome.PASS),
    ]

    summary = compute_evaluation_summary(records, k_values=[1, 2])
    assert summary.total_tasks == 2
    assert summary.total_trials == 4
    assert summary.overall_success_rate == 0.75  # 3 / 4

    # Cancellation had 2 passes out of 2 = 1.0
    assert summary.category_success_rates["cancellation"] == 1.0
    # Refund had 1 pass out of 2 = 0.5
    assert summary.category_success_rates["refund"] == 0.5

    # Easy had 1.0, Hard had 0.5
    assert summary.difficulty_success_rates["easy"] == 1.0
    assert summary.difficulty_success_rates["hard"] == 0.5
