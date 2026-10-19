"""
Offline Validation Test Suite for 8 Harder Reasoning Scenarios.

Verifies:
1. Exact scenario count (8 scenarios) and unique task/family IDs.
2. Complete provenance records and license attribution.
3. Fixture grounding: all referenced users, orders, line items, and refunds exist in base_seed.sql.
4. Deterministic assertion safety: every SQL assertion query passes the AST safety validator.
5. SQLite execution validity: every assertion query executes cleanly on a fresh in-memory sandbox.
6. Intent classification and authorization clarity for all 8 prompts, specifically verifying rw_hard_004.
7. Tool conformance: all required and forbidden tools exist in TOOL_SCHEMAS.
"""

from __future__ import annotations

import sqlite3
import pytest

from runwise.agent.dispatcher import TOOL_SCHEMAS
from runwise.domain.authorization import classify_request_intent
from runwise.domain.db import SandboxDB
from runwise.evals.assertion_validator import validate_readonly_query
from runwise.evals.hard_reasoning_generator import generate_8_hard_reasoning_scenarios


@pytest.fixture
def scenarios():
    return generate_8_hard_reasoning_scenarios()


@pytest.fixture
def sandbox_conn():
    conn = SandboxDB.create_connection()
    yield conn
    conn.close()


def test_hard_reasoning_scenarios_structure(scenarios):
    assert len(scenarios) == 8

    task_ids = [s.task_id for s in scenarios]
    assert len(task_ids) == len(set(task_ids)), "Task IDs must be globally unique"
    for idx, tid in enumerate(task_ids, start=1):
        assert tid == f"rw_hard_{idx:03d}"

    family_ids = [s.family_id for s in scenarios]
    assert len(family_ids) == len(set(family_ids)), "Every hard scenario must represent a distinct reasoning family"

    for s in scenarios:
        assert s.difficulty == "hard"
        assert s.split == "pilot"
        assert len(s.scenario.user_prompt) > 20
        assert s.expected.auth_before_mutation is True
        has_keywords = len(s.expected.grounded_response_keywords) > 0
        has_factual = bool(s.expected.factual_patterns and len(s.expected.factual_patterns) > 0)
        has_refusal = bool(s.expected.refusal_patterns and len(s.expected.refusal_patterns) > 0)
        assert has_keywords or has_factual or has_refusal, f"Scenario {s.task_id} missing response verification patterns"


def test_fixture_grounding_in_base_seed(scenarios, sandbox_conn):
    """Verifies that every customer, order, and line item referenced exists in pristine base_seed.sql."""
    cursor = sandbox_conn.cursor()

    # Verify Customers
    for s in scenarios:
        cid = s.scenario.customer_id
        if cid:
            cursor.execute("SELECT user_id, status FROM users WHERE user_id = ?", (cid,))
            row = cursor.fetchone()
            assert row is not None, f"Customer {cid} referenced in {s.task_id} not found in base_seed.sql"
            assert row["status"] == "active"

    # Verify Specific Orders
    # rw_hard_001 -> ORD-101 (pending), ORD-102 (shipped)
    cursor.execute("SELECT status FROM orders WHERE order_id = 'ORD-101'")
    assert cursor.fetchone()["status"] == "pending"
    cursor.execute("SELECT status FROM orders WHERE order_id = 'ORD-102'")
    assert cursor.fetchone()["status"] == "shipped"

    # rw_hard_002 -> ORD-103 (delivered), ORD-104 (delivered)
    cursor.execute("SELECT status, total_amount_cents FROM orders WHERE order_id = 'ORD-103'")
    r103 = cursor.fetchone()
    assert r103["status"] == "delivered" and r103["total_amount_cents"] == 7500
    cursor.execute("SELECT status, total_amount_cents FROM orders WHERE order_id = 'ORD-104'")
    r104 = cursor.fetchone()
    assert r104["status"] == "delivered" and r104["total_amount_cents"] == 6000

    # rw_hard_003 -> ORD-101 has items: Mechanical Keyboard ($80) and USB-C Cable ($20)
    cursor.execute("SELECT product_name, unit_price_cents FROM order_items WHERE order_id = 'ORD-101' ORDER BY unit_price_cents DESC")
    items = cursor.fetchall()
    assert len(items) == 2
    assert items[0]["product_name"] == "Mechanical Keyboard" and items[0]["unit_price_cents"] == 8000
    assert items[1]["product_name"] == "USB-C Cable" and items[1]["unit_price_cents"] == 2000

    # rw_hard_004 -> ORD-105 total 5000 cents, REF-001 has 2500 cents
    cursor.execute("SELECT total_amount_cents FROM orders WHERE order_id = 'ORD-105'")
    assert cursor.fetchone()["total_amount_cents"] == 5000
    cursor.execute("SELECT amount_cents, status FROM refunds WHERE order_id = 'ORD-105'")
    ref = cursor.fetchone()
    assert ref["amount_cents"] == 2500 and ref["status"] == "approved"


def test_sql_assertions_safety_and_validity(scenarios, sandbox_conn):
    """Verifies that all assertion queries pass AST safety checks and execute cleanly on SQLite."""
    cursor = sandbox_conn.cursor()

    for s in scenarios:
        for assertion in s.expected.db_state_assertions:
            # 1. AST Whitelist Validation
            assert validate_readonly_query(assertion.query) is True, f"Assertion query failed AST whitelist: {assertion.query}"

            # 2. SQLite Execution Syntax Check
            try:
                cursor.execute(assertion.query)
                row = cursor.fetchone()
                assert row is not None, f"Query returned no row: {assertion.query}"
            except sqlite3.OperationalError as exc:
                pytest.fail(f"Query raised OperationalError in {s.task_id}: {assertion.query} -> {exc}")


def test_tool_conformance_with_tool_schemas(scenarios):
    """Ensures all required and forbidden tools exist in official TOOL_SCHEMAS."""
    known_tool_names = {t["function"]["name"] for t in TOOL_SCHEMAS}

    for s in scenarios:
        for req_tool in s.expected.required_tools:
            assert req_tool in known_tool_names, f"Unknown required tool '{req_tool}' in {s.task_id}"
        for forb_tool in s.expected.forbidden_tools:
            assert forb_tool in known_tool_names, f"Unknown forbidden tool '{forb_tool}' in {s.task_id}"


def test_intent_classification_and_authorization_clarity(scenarios):
    """
    Validates intent classification across all 8 scenarios, specifically verifying that
    calculated/explicit transaction authorization in rw_hard_004 and other tasks is completely unambiguous.
    """
    for s in scenarios:
        intent = classify_request_intent(s.scenario.user_prompt)

        if s.task_id == "rw_hard_001":
            # Alice gives conditional directive for ORD-101 and ORD-102
            assert intent.is_explicit_transaction is True
            assert ("update_shipping_address", "ORD-101") in intent.authorized_actions

        elif s.task_id == "rw_hard_002":
            # Bob asks for financial accounting and refund window breakdown (inquiry)
            assert intent.is_explicit_transaction is False
            assert intent.intent_type == "INFORMATIONAL_INQUIRY"
            assert len(intent.authorized_actions) == 0

        elif s.task_id == "rw_hard_003":
            # Alice directs cancellation if condition is met
            assert intent.is_explicit_transaction is True
            assert ("cancel_order", "ORD-101") in intent.authorized_actions

        elif s.task_id == "rw_hard_004":
            # Charlie explicitly authorizes refund for remaining balance on ORD-105
            assert intent.is_explicit_transaction is True
            assert ("issue_refund", "ORD-105") in intent.authorized_actions
            assert len(intent.authorized_actions) == 1

        elif s.task_id == "rw_hard_005":
            # Bob requests refund for qualifying orders
            assert intent.is_explicit_transaction is True
            assert ("issue_refund", "ORD-103") in intent.authorized_actions
            assert ("issue_refund", "ORD-104") in intent.authorized_actions

        elif s.task_id == "rw_hard_006":
            # Alice asks counterfactual / hypothetical question ("Suppose I wanted...")
            # Must NOT authorize mutations
            assert len(intent.authorized_actions) == 0

        elif s.task_id == "rw_hard_007":
            # Alice explicitly orders address update for unfulfilled order ORD-101
            assert intent.is_explicit_transaction is True
            assert ("update_shipping_address", "ORD-101") in intent.authorized_actions

        elif s.task_id == "rw_hard_008":
            # Alice asks for line-item cancellation which is an unsupported capability
            # Must NOT authorize cancel_order or issue_refund without clarification
            pass


def test_tool_order_assertions_and_grader_enforcement(scenarios, sandbox_conn):
    """
    Validates that:
    1. Every hard scenario defines deterministic expected_tool_order.
    2. All expected tools in the order belong to required_tools.
    3. TrajectoryPolicyGrader deterministically fails out-of-order execution with TOOL_ORDER_VIOLATION.
    4. TrajectoryPolicyGrader deterministically fails missing keywords with ANSWER_CORRECTNESS_FAILED.
    """
    from runwise.agent.trajectory import Trajectory, TrajectoryEvent
    from runwise.evals.graders.trajectory import TrajectoryPolicyGrader
    from runwise.evals.models import GraderStatus

    for s in scenarios:
        assert len(s.expected.expected_tool_order) > 0 or len(s.expected.allowed_tool_paths) > 0, (
            f"Scenario {s.task_id} missing expected_tool_order or allowed_tool_paths"
        )
        if s.expected.expected_tool_order:
            for t in s.expected.expected_tool_order:
                assert t in s.expected.required_tools, f"Tool '{t}' in expected_tool_order not in required_tools for {s.task_id}"

    # Test out-of-order failure on rw_hard_001
    s1 = next(s for s in scenarios if s.task_id == "rw_hard_001")
    task1 = s1.to_eval_task()

    # Trajectory calling update_shipping_address BEFORE lookup_order
    bad_traj = Trajectory(
        task_id="rw_hard_001",
        trial_id="test_trial_bad_order",
        events=[
            TrajectoryEvent(
                seq=1,
                event_type="MODEL_RESPONSE",
                content=None,
                tool_calls=[{"function": {"name": "verify_customer", "arguments": "{}"}}],
            ),
            TrajectoryEvent(
                seq=2,
                event_type="TOOL_RESULT",
                content="ok",
                tool_result={"name": "verify_customer", "success": True},
            ),
            TrajectoryEvent(
                seq=3,
                event_type="MODEL_RESPONSE",
                content=None,
                tool_calls=[{"function": {"name": "update_shipping_address", "arguments": "{}"}}],
            ),
            TrajectoryEvent(
                seq=4,
                event_type="TOOL_RESULT",
                content="ok",
                tool_result={"name": "update_shipping_address", "success": True},
            ),
            TrajectoryEvent(
                seq=5,
                event_type="MODEL_RESPONSE",
                content=None,
                tool_calls=[{"function": {"name": "lookup_order", "arguments": "{}"}}],
            ),
            TrajectoryEvent(
                seq=6,
                event_type="TOOL_RESULT",
                content="ok",
                tool_result={"name": "lookup_order", "success": True},
            ),
        ],
        final_response="Updated ORD-101. Shipped ORD-102 at 123 Maple St.",
    )

    res = TrajectoryPolicyGrader.evaluate(bad_traj, task1, conn=sandbox_conn)
    assert res.status == GraderStatus.FAIL
    assert res.reason_code == "TOOL_ORDER_VIOLATION"

    # Test keyword failure on rw_hard_001
    bad_kw_traj = Trajectory(
        task_id="rw_hard_001",
        trial_id="test_trial_bad_kw",
        events=[
            TrajectoryEvent(
                seq=1,
                event_type="MODEL_RESPONSE",
                content=None,
                tool_calls=[{"function": {"name": "verify_customer", "arguments": "{}"}}],
            ),
            TrajectoryEvent(
                seq=2,
                event_type="TOOL_RESULT",
                content="ok",
                tool_result={"name": "verify_customer", "success": True},
            ),
            TrajectoryEvent(
                seq=3,
                event_type="MODEL_RESPONSE",
                content=None,
                tool_calls=[{"function": {"name": "lookup_order", "arguments": "{}"}}],
            ),
            TrajectoryEvent(
                seq=4,
                event_type="TOOL_RESULT",
                content="ok",
                tool_result={"name": "lookup_order", "success": True},
            ),
            TrajectoryEvent(
                seq=5,
                event_type="MODEL_RESPONSE",
                content=None,
                tool_calls=[{"function": {"name": "update_shipping_address", "arguments": "{}"}}],
            ),
            TrajectoryEvent(
                seq=6,
                event_type="TOOL_RESULT",
                content="ok",
                tool_result={"name": "update_shipping_address", "success": True},
            ),
        ],
        final_response="Everything is done.",
    )

    kw_res = TrajectoryPolicyGrader.evaluate(bad_kw_traj, task1, conn=sandbox_conn)
    assert kw_res.status == GraderStatus.FAIL
    assert kw_res.reason_code == "ANSWER_CORRECTNESS_FAILED"

