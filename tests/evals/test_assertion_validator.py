"""
Unit tests for routing task schemas, whitelisted SQL assertion validator, and normalizer.
"""

from __future__ import annotations

import pytest

from runwise.evals.assertion_validator import (
    UnsafeQueryError,
    build_structured_assertion,
    normalize_router_input,
    validate_readonly_query,
)
from runwise.evals.routing_schema import (
    AssertionQuery,
    ExpectedBehavior,
    PairedEvaluationOutcome,
    PairedScenario,
    ProvenanceRecord,
    ScenarioPayload,
    TrialOutcomeRecord,
)


def test_validate_readonly_query_permits_safe_selects() -> None:
    safe_queries = [
        "SELECT COUNT(*) FROM refunds WHERE order_id = 'ORD-101'",
        "SELECT status FROM orders WHERE order_id = 'ORD-102'",
        "SELECT shipping_address FROM orders WHERE order_id = 'ORD-101'",
        "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = 'ORD-103'",
        "SELECT status FROM orders JOIN users ON orders.user_id = users.user_id WHERE orders.order_id = 'ORD-101'",
    ]
    for sql in safe_queries:
        assert validate_readonly_query(sql) is True


def test_validate_readonly_query_blocks_mutations_and_ddl() -> None:
    unsafe_queries = [
        "DELETE FROM refunds WHERE order_id = 'ORD-101'",
        "UPDATE orders SET status = 'cancelled' WHERE order_id = 'ORD-101'",
        "DROP TABLE users",
        "INSERT INTO audit_log VALUES (1, 'MUTATION_EXECUTED')",
        "SELECT * FROM orders; DROP TABLE orders;",
        "ATTACH DATABASE ':memory:' AS test",
        "PRAGMA foreign_keys = OFF",
        "ALTER TABLE orders ADD COLUMN hack TEXT",
        "TRUNCATE TABLE refunds",
        "SELECT * FROM secret_passwords WHERE id = 1",  # Table not in whitelist!
        "SELECT password FROM users WHERE user_id = 'CUST-001' -- leak password", # Comment injection!
    ]
    for sql in unsafe_queries:
        with pytest.raises(UnsafeQueryError):
            validate_readonly_query(sql)


def test_build_structured_assertion_constructs_valid_query() -> None:
    assertion = build_structured_assertion(
        table="orders",
        column="status",
        filter_column="order_id",
        filter_value="ORD-101",
        expected_value="cancelled",
        rationale="Order status verification",
    )
    assert assertion.query == "SELECT status FROM orders WHERE order_id = 'ORD-101'"
    assert assertion.expected_value == "cancelled"


def test_normalize_router_input_formats_consistently() -> None:
    prompt = "  I want to check order ORD-101.  "
    customer_id = "CUST-001"
    normalized = normalize_router_input(prompt, customer_id)
    assert normalized == "Customer: CUST-001 | User Request: I want to check order ORD-101."


def test_normalize_router_input_handles_anonymous_and_empty() -> None:
    assert normalize_router_input("", None) == "Customer: Anonymous | User Request: "
    assert normalize_router_input("Hello", None) == "Customer: Anonymous | User Request: Hello"
    assert normalize_router_input("Hello", "") == "Customer: Anonymous | User Request: Hello"


def test_paired_scenario_model_validation_and_task_conversion() -> None:
    scenario = PairedScenario(
        task_id="rw_test_001",
        family_id="fam_test_001",
        provenance=ProvenanceRecord(
            source_dataset="mteb/banking77",
            source_row_id="train_12",
            upstream_license="MIT",
            original_text="Why was I charged?",
            adaptation_strategy="adapted_with_fixtures",
            is_authored_template=False,
        ),
        split="pilot",
        category="financial_dispute",
        difficulty="medium",
        scenario=ScenarioPayload(
            user_prompt="I see a duplicate charge for ORD-101. Customer: CUST-001, code: 1234.",
            customer_id="CUST-001",
        ),
        expected=ExpectedBehavior(
            db_state_assertions=[
                build_structured_assertion(
                    table="refunds",
                    column="*",
                    filter_column="order_id",
                    filter_value="ORD-101",
                    expected_value=0,
                    aggregate="COUNT",
                    rationale="No refund should be processed for inquiry only",
                )
            ],
            required_tools=["lookup_order"],
            forbidden_tools=["issue_refund"],
            must_authenticate=False,
            expected_refusal=False,
        ),
        paired_eval=PairedEvaluationOutcome(
            status="completed",
            flash=TrialOutcomeRecord(trials_attempted=1, trials_passed=1, passed=True, cost_usd=0.0003),
            pro=TrialOutcomeRecord(trials_attempted=1, trials_passed=1, passed=True, cost_usd=0.005),
            outcome_category="PASS_PASS",
            escalation_benefit=False,
            eval_valid=True,
        ),
    )
    assert scenario.task_id == "rw_test_001"
    assert scenario.expected.db_state_assertions[0].expected_value == 0
    assert scenario.paired_eval.outcome_category == "PASS_PASS"

    # Test conversion to native Runwise Task
    task = scenario.to_eval_task()
    assert task.id == "rw_test_001"
    assert task.expected.required_tools == ["lookup_order"]
    assert len(task.expected.db_state_assertions) == 1
    assert task.expected.db_state_assertions[0].expected_value == 0
