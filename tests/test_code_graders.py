"""
Unit tests for Tier 1 code graders (DBStateGrader and SafetyInvariantAuditor).
"""

from runwise.domain.db import SandboxDB
from runwise.evals.graders.code import DBStateGrader, SafetyInvariantAuditor
from runwise.evals.models import DBAssertion, GraderStatus


def test_db_state_grader_pass():
    """Verify grader passes when database state matches expectations."""
    conn = SandboxDB.create_connection()

    assertions = [
        DBAssertion(
            query="SELECT status FROM orders WHERE order_id = 'ORD-101'",
            expected_value="pending",
            operator="equals",
            rationale="Order ORD-101 should start pending",
        ),
        DBAssertion(
            query="SELECT total_amount_cents FROM orders WHERE order_id = 'ORD-101'",
            expected_value=5000,
            operator="greater_than",
            rationale="Order total should exceed $50",
        ),
    ]

    result = DBStateGrader.evaluate(conn, assertions)
    assert result.status == GraderStatus.PASS
    assert result.reason_code == "ALL_ASSERTIONS_PASSED"
    assert result.evidence["passed"] == 2


def test_db_state_grader_fail():
    """Verify grader fails with detailed evidence when state deviates."""
    conn = SandboxDB.create_connection()

    assertions = [
        DBAssertion(
            query="SELECT status FROM orders WHERE order_id = 'ORD-101'",
            expected_value="cancelled",  # In reality it is 'pending'
            operator="equals",
            rationale="Expect order to be cancelled",
        )
    ]

    result = DBStateGrader.evaluate(conn, assertions)
    assert result.status == GraderStatus.FAIL
    assert result.reason_code == "ASSERTION_FAILED"
    assert len(result.evidence["failures"]) == 1
    assert result.evidence["failures"][0]["actual"] == "pending"


def test_db_state_grader_sql_error():
    """Verify SQL syntax errors report ERROR (harness bug) without blaming agent."""
    conn = SandboxDB.create_connection()

    assertions = [
        DBAssertion(
            query="SELECT non_existent_column FROM bad_table_syntax",
            expected_value="anything",
        )
    ]

    result = DBStateGrader.evaluate(conn, assertions)
    assert result.status == GraderStatus.ERROR
    assert result.reason_code == "SQL_EXECUTION_ERROR"


def test_safety_auditor_pass_on_clean_db():
    """Verify safety auditor passes on a pristine seeded database."""
    conn = SandboxDB.create_connection()
    result = SafetyInvariantAuditor.evaluate(conn)

    assert result.status == GraderStatus.PASS
    assert result.reason_code == "ALL_INVARIANTS_HELD"


def test_safety_auditor_fails_on_invariant_breach():
    """Verify safety auditor catches an explicit INVARIANT_BREACH in audit log."""
    conn = SandboxDB.create_connection()
    conn.execute(
        """
        INSERT INTO audit_log (
            trial_id, event_type, tool_name, user_id, order_id, status_code, details_json, timestamp
        ) VALUES (
            'trial_test', 'INVARIANT_BREACH', 'issue_refund', 'CUST-001', 'ORD-101', 'FAILED', '{}', 1700000000
        );
        """
    )
    conn.commit()

    result = SafetyInvariantAuditor.evaluate(conn)
    assert result.status == GraderStatus.FAIL
    assert result.reason_code == "INVARIANT_BREACH_DETECTED"
