"""
Unit tests for the 30-scenario diagnostic pilot generator, contamination prevention,
and hard budget pre-flight safety gates.
"""

from __future__ import annotations

import pytest

from runwise.evals.pilot_generator import (
    check_contamination_and_near_duplicates,
    estimate_pilot_cost,
    generate_30_scenario_pilot,
)
from runwise.evals.pilot_runner import (
    PilotApprovalError,
    run_paired_pilot,
)


def test_generate_30_scenario_pilot_creates_exact_distribution() -> None:
    scenarios = generate_30_scenario_pilot()
    assert len(scenarios) == 30

    # Verify task ID uniqueness
    task_ids = [s.task_id for s in scenarios]
    assert len(task_ids) == len(set(task_ids)), "Task IDs must be globally unique"

    # Verify category distribution
    categories = {s.category for s in scenarios}
    assert "inquiry" in categories
    assert "cancellation" in categories
    assert "financial_dispute" in categories
    assert "conditional_mutation" in categories

    # Verify family ID grouping exists on every scenario
    for s in scenarios:
        assert s.family_id is not None and len(s.family_id) > 0


def test_check_contamination_and_near_duplicates_guards_against_leakage() -> None:
    scenarios = generate_30_scenario_pilot()
    
    # 1. Pilot scenarios must not contain holdout tasks
    is_clean, issues = check_contamination_and_near_duplicates(scenarios)
    assert is_clean is True
    assert len(issues) == 0

    # 2. Synthetic leak injection test: duplicate family or identical prompt text
    from runwise.evals.routing_schema import (
        AssertionQuery,
        ExpectedBehavior,
        PairedScenario,
        ProvenanceRecord,
        ScenarioPayload,
    )
    duplicate_scenario = PairedScenario(
        task_id="rw_leak_test",
        family_id=scenarios[0].family_id, # Reusing family_id in separate split!
        provenance=ProvenanceRecord(
            source_dataset="test",
            source_row_id="1",
            original_text=scenarios[0].scenario.user_prompt, # Identical prompt!
            adaptation_strategy="leak",
        ),
        split="test",
        category="inquiry",
        difficulty="easy",
        scenario=ScenarioPayload(user_prompt=scenarios[0].scenario.user_prompt),
        expected=ExpectedBehavior(),
    )
    is_clean_leaked, issues_leaked = check_contamination_and_near_duplicates(scenarios + [duplicate_scenario])
    assert is_clean_leaked is False
    assert len(issues_leaked) > 0


def test_estimate_pilot_cost_stays_within_budget_target() -> None:
    scenarios = generate_30_scenario_pilot()
    cost_est = estimate_pilot_cost(scenarios, repeat_count=5, repeat_trials=3)

    assert cost_est["flash_calls"] == 45
    assert cost_est["pro_calls"] == 45
    assert cost_est["total_estimated_usd"] <= 0.50
    assert cost_est["flash_estimated_usd"] > 0.0
    assert cost_est["pro_estimated_usd"] > cost_est["flash_estimated_usd"]


def test_pilot_runner_requires_explicit_approval_flag() -> None:
    scenarios = generate_30_scenario_pilot()
    with pytest.raises(PilotApprovalError, match="Paid pilot execution blocked"):
        run_paired_pilot(scenarios, approved_by_user=False)
