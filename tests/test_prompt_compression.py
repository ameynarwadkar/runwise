"""
Unit and Integration Tests for Prompt Optimization and Invariant Preservation.
"""

from __future__ import annotations

from types import SimpleNamespace
import pytest

from runwise.agent.loop import AgentLoop, _load_system_prompt
from runwise.evals.models import Task, TaskExpected, TrialOutcome
from runwise.evals.runner import run_single_trial
from runwise.service.cost import calculate_cost_breakdown, format_cost_table


def test_trimmed_prompt_loads_and_is_significantly_smaller():
    base = _load_system_prompt("v1.0")
    trimmed = _load_system_prompt("v1.1_trimmed")

    assert len(base) > 0
    assert len(trimmed) > 0

    # Verify at least 35% character reduction
    reduction_pct = (len(base) - len(trimmed)) / len(base) * 100
    assert reduction_pct >= 35.0, f"Expected >= 35% reduction, got {reduction_pct:.1f}%"


def test_trimmed_prompt_preserves_all_critical_invariants():
    trimmed = _load_system_prompt("v1.1_trimmed")

    # Critical security and auth invariants
    assert "verify_customer" in trimmed
    assert "cancel_order" in trimmed
    assert "update_shipping_address" in trimmed
    assert "issue_refund" in trimmed
    assert "lookup_order" in trimmed
    assert "lookup_user" in trimmed

    # Policy status gates
    assert "pending" in trimmed
    assert "delivered" in trimmed
    assert "30 days" in trimmed

    # Idempotency and fallback defaults
    assert "idempotency_key" in trimmed
    assert "reason" in trimmed


def test_trimmed_prompt_cost_reduction_math():
    # Prompt tokens before and after
    b_base = calculate_cost_breakdown("gemini-2.5-flash", prompt_tokens=750, completion_tokens=60)
    b_opt = calculate_cost_breakdown("gemini-2.5-flash", prompt_tokens=450, completion_tokens=60)

    # Cost reduction must exceed 20%
    cost_drop_pct = (b_base.total_cost_usd - b_opt.total_cost_usd) / b_base.total_cost_usd * 100
    assert cost_drop_pct >= 25.0

    table = format_cost_table(b_base, b_opt)
    assert "Optimized / Trimmed" in table
    assert "-40.0%" in table


def test_runner_executes_cleanly_with_trimmed_prompt():
    task = Task(
        id="t_trim_01",
        split="ci",
        category="inquiry",
        difficulty="easy",
        user_prompt="Status of ORD-999?",
        expected=TaskExpected(required_tools=["lookup_order"]),
    )

    tc = SimpleNamespace(id="c1", function=SimpleNamespace(name="lookup_order", arguments={"order_id": "ORD-999"}))
    msg1 = SimpleNamespace(content=None, tool_calls=[tc])
    msg2 = SimpleNamespace(content="Order ORD-999 is pending.", tool_calls=None)
    usage = SimpleNamespace(prompt_tokens=400, completion_tokens=20)

    turn1 = SimpleNamespace(choices=[SimpleNamespace(message=msg1)], usage=usage)
    turn2 = SimpleNamespace(choices=[SimpleNamespace(message=msg2)], usage=usage)

    record, trajectory = run_single_trial(
        task=task,
        trial_idx=1,
        prompt_version="v1.1_trimmed",
        mock_completions=[turn1, turn2],
    )

    assert record.outcome == TrialOutcome.PASS
    assert trajectory.metadata.get("model") is not None
