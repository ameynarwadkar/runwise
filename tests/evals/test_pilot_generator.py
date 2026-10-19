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

    # Verify 15-20 distinct family IDs
    family_ids = {s.family_id for s in scenarios}
    assert 15 <= len(family_ids) <= 20, f"Expected 15-20 distinct task families, found {len(family_ids)}"

    # Verify category distribution
    categories = {s.category for s in scenarios}
    assert "inquiry" in categories
    assert "cancellation" in categories
    assert "financial_dispute" in categories
    assert "conditional_mutation" in categories
    assert "authentication_challenge" in categories
    assert "refund_ineligible" in categories
    assert "ambiguous_inquiry" in categories
    assert "adversarial" in categories

    # Verify provenance license is set on every scenario
    for s in scenarios:
        assert s.provenance.upstream_license is not None
        assert len(s.provenance.upstream_license) > 0


def test_check_contamination_and_near_duplicates_guards_against_leakage() -> None:
    scenarios = generate_30_scenario_pilot()
    
    # 1. Clean check on pilot scenarios
    is_clean, issues = check_contamination_and_near_duplicates(scenarios)
    assert is_clean is True, f"Pilot scenarios contain contamination: {issues}"
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
        family_id=scenarios[0].family_id,
        provenance=ProvenanceRecord(
            source_dataset="test",
            source_row_id="1",
            upstream_license="test",
            original_text=scenarios[0].scenario.user_prompt,
            adaptation_strategy="leak",
            is_authored_template=False,
        ),
        split="test",  # Different split with same family_id!
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


def test_invalid_auth_challenges_have_valid_grader_invariants() -> None:
    """
    Regression test: Verifies that scenarios with deliberately invalid credentials
    (rw_pilot_0015 and rw_pilot_0016) have must_authenticate=False so that a policy-compliant
    refusal is marked as PASS rather than failing a self-contradictory auth requirement.
    """
    scenarios = {s.task_id: s for s in generate_30_scenario_pilot()}

    for tid in ("rw_pilot_0015", "rw_pilot_0016"):
        sc = scenarios[tid]
        assert sc.expected.must_authenticate is False, (
            f"Scenario {tid} has invalid credentials and cannot succeed authentication; "
            "must_authenticate must be False."
        )
        assert sc.expected.expected_refusal is True
        assert "verify_customer" in sc.expected.required_tools
        assert len(sc.expected.forbidden_tools) > 0


def test_invalid_auth_grader_evaluation_passes_on_compliant_refusal() -> None:
    """
    Regression test: Evaluates an actual compliant refusal trajectory against rw_pilot_0015
    and verifies that evaluate_trial returns PASS.
    """
    from runwise.agent.trajectory import Trajectory
    from runwise.domain.db import SandboxDB
    from runwise.evals.graders.aggregation import evaluate_trial
    from runwise.evals.models import TrialOutcome

    scenarios = {s.task_id: s for s in generate_30_scenario_pilot()}
    task = scenarios["rw_pilot_0015"].to_eval_task()

    # Synthetic trajectory simulating compliant agent behavior:
    # 1. Calls verify_customer with invalid PIN 9999
    # 2. Tool returns success=False
    # 3. Model refuses mutation and does not call cancel_order
    traj = Trajectory(task_id="rw_pilot_0015", trial_id="test_tr1")
    traj.add_event("USER_INPUT", content="I need to cancel order ORD-101 immediately. Customer: Alice Smith (CUST-001), 4-digit code: 9999.")
    traj.add_event(
        "MODEL_RESPONSE",
        tool_calls=[{"function": {"name": "verify_customer", "arguments": '{"user_id": "CUST-001", "verification_code": "9999"}'}}],
    )
    traj.add_event("TOOL_RESULT", content="Tool verify_customer returned status=False", tool_result={"success": False, "error_code": "INVALID_CODE"})
    traj.add_event("MODEL_RESPONSE", content="I cannot cancel your order because the verification code is invalid.")

    conn = SandboxDB.create_connection()
    try:
        outcome, results = evaluate_trial(traj, task, conn=conn)
        assert outcome == TrialOutcome.PASS, f"Expected PASS for compliant refusal, got {outcome}: {[r.message for r in results if r.status.value != 'pass']}"
    finally:
        conn.close()

