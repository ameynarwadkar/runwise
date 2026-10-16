"""
Unit tests for domain tools: verifies authentication enforcement, policy rules,
cumulative refund calculations, and idempotency guarantees.
"""

from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext
from runwise.domain.tools import (
    cancel_order,
    issue_refund,
    lookup_order,
    lookup_user,
    update_shipping_address,
    verify_customer,
)

# Deterministic frozen clock matching our design specification
FROZEN_CLOCK = "2026-10-15T12:00:00Z"


def create_test_session(authenticated_user_id: str | None = None) -> SessionContext:
    """Helper to spin up an ephemeral sandbox connection and session."""
    conn = SandboxDB.create_connection()
    return SessionContext(
        conn=conn,
        trial_id="trial_tool_test_01",
        current_time_iso=FROZEN_CLOCK,
        authenticated_user_id=authenticated_user_id,
    )


def test_lookup_user_unauthorized_does_not_authenticate():
    """Verify lookup_user returns profile data but does NOT grant session auth."""
    session = create_test_session()
    result = lookup_user(session, user_id="CUST-001")

    assert result.success is True
    assert result.data["email"] == "alice@example.com"
    # Session must still be unauthorized
    assert session.authenticated_user_id is None
    assert session.is_authorized("CUST-001") is False


def test_verify_customer_authenticates_session():
    """Verify valid verification code authorizes the session and writes an audit event."""
    session = create_test_session()
    result = verify_customer(session, user_id="CUST-001", verification_code="1234")

    assert result.success is True
    assert session.authenticated_user_id == "CUST-001"
    assert session.is_authorized("CUST-001") is True

    # Verify audit log recorded AUTH_VERIFIED
    logs = SandboxDB.get_audit_log(session.conn, trial_id=session.trial_id)
    assert any(log["event_type"] == "AUTH_VERIFIED" for log in logs)


def test_cancel_order_requires_auth():
    """Unauthenticated cancel_order must be blocked and recorded as MUTATION_BLOCKED."""
    session = create_test_session(authenticated_user_id=None)
    result = cancel_order(session, order_id="ORD-101", reason="Changed mind", idempotency_key="k1")

    assert result.success is False
    assert result.error_code == "AUTH_REQUIRED"

    # Verify audit log caught the blocked attempt
    logs = SandboxDB.get_audit_log(session.conn, trial_id=session.trial_id)
    assert any(log["event_type"] == "MUTATION_BLOCKED" and log["status_code"] == "AUTH_REQUIRED" for log in logs)


def test_cancel_order_success():
    """Authenticated cancellation of a pending order succeeds and updates DB."""
    session = create_test_session(authenticated_user_id="CUST-001")
    result = cancel_order(session, order_id="ORD-101", reason="No longer needed", idempotency_key="k2")

    assert result.success is True
    assert result.data["status"] == "cancelled"

    # Verify DB state mutated
    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "cancelled"


def test_cancel_shipped_order_blocked():
    """Cancelling a shipped order (ORD-102) must be blocked by policy invariant."""
    session = create_test_session(authenticated_user_id="CUST-001")
    result = cancel_order(session, order_id="ORD-102", reason="Too late", idempotency_key="k3")

    assert result.success is False
    assert result.error_code == "ORDER_NOT_PENDING"

    # Verify DB state was NOT modified
    order = SandboxDB.get_order(session.conn, "ORD-102")
    assert order["status"] == "shipped"


def test_refund_window_expired_blocked():
    """ORD-104 was delivered in August (>30 days before Oct 15). Refund must be blocked."""
    session = create_test_session(authenticated_user_id="CUST-002")
    result = issue_refund(
        session, order_id="ORD-104", amount_cents=1000, reason="Defective", idempotency_key="k4"
    )

    assert result.success is False
    assert result.error_code == "WINDOW_EXPIRED"


def test_cumulative_refund_limit_enforced():
    """
    ORD-105 total is $50.00 (5000 cents) and already has a $25.00 partial refund.
    Requesting $30.00 (3000 cents) must fail with LIMIT_EXCEEDED.
    Requesting $25.00 (2500 cents) must succeed.
    """
    session = create_test_session(authenticated_user_id="CUST-003")

    # Attempt $30.00 refund (exceeds remaining balance of $25.00)
    over_limit = issue_refund(
        session, order_id="ORD-105", amount_cents=3000, reason="High refund", idempotency_key="k5_fail"
    )
    assert over_limit.success is False
    assert over_limit.error_code == "LIMIT_EXCEEDED"

    # Attempt exact remaining balance ($25.00)
    exact_balance = issue_refund(
        session, order_id="ORD-105", amount_cents=2500, reason="Exact remaining", idempotency_key="k5_pass"
    )
    assert exact_balance.success is True
    assert exact_balance.data["amount_cents"] == 2500


def test_refund_idempotency_deduplication():
    """Calling issue_refund twice with identical idempotency_key returns existing refund."""
    session = create_test_session(authenticated_user_id="CUST-002")

    # ORD-103 was delivered recently, eligible for refund
    res1 = issue_refund(
        session, order_id="ORD-103", amount_cents=1000, reason="Item broken", idempotency_key="idemp_key_999"
    )
    assert res1.success is True
    refund_id_1 = res1.data["refund_id"]

    # Call again with the exact same idempotency key (simulating retry)
    res2 = issue_refund(
        session, order_id="ORD-103", amount_cents=1000, reason="Item broken", idempotency_key="idemp_key_999"
    )
    assert res2.success is True
    assert res2.data["refund_id"] == refund_id_1

    # Assert exactly ONE refund was inserted into the database
    cursor = session.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM refunds WHERE idempotency_key = 'idemp_key_999'")
    count = cursor.fetchone()[0]
    assert count == 1
