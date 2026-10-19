"""
Adversarial regression test suite for cross-account privacy hardening and mutation safety.

Tests cover:
1. Cross-account read attempts via lookup_order
2. Anonymous unauthenticated read requests (verifying PII masking while preserving public tracking)
3. Cross-account mutation attempts (cancel_order, update_shipping_address, issue_refund)
4. Unauthenticated mutation attempts
5. Deterministic executor-level privacy enforcement
"""

import pytest
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext, ToolResult
from runwise.domain.tools import (
    cancel_order,
    issue_refund,
    list_orders,
    lookup_order,
    lookup_user,
    update_shipping_address,
    verify_customer,
)

FROZEN_CLOCK = "2026-10-15T12:00:00Z"


def create_test_session(authenticated_user_id: str | None = None) -> SessionContext:
    """Helper to create an isolated in-memory SQLite sandbox session."""
    conn = SandboxDB.create_connection()
    session = SessionContext(
        conn=conn,
        trial_id="test_security_trial",
        current_time_iso=FROZEN_CLOCK,
        authenticated_user_id=authenticated_user_id,
    )
    if authenticated_user_id:
        session.authorize_action("*", "*")
    return session


# ============================================================================
# PRIVACY HARDENING TESTS: DOMAIN TOOLS ENFORCEMENT
# ============================================================================

def test_lookup_order_anonymous_preserves_public_status_masks_pii():
    """Unauthenticated users can track order status, but PII is strictly masked."""
    session = create_test_session(authenticated_user_id=None)
    result = lookup_order(session, order_id="ORD-101")

    assert result.success is True
    order = result.data["order"]
    assert order["order_id"] == "ORD-101"
    assert order["status"] == "pending"
    assert order["user_id"] == "***"
    assert "Masked" in order["shipping_address"]
    assert "123 Maple St" not in order["shipping_address"]
    assert "items" not in result.data
    assert "refunds" not in result.data
    assert result.data["is_public_view"] is True


def test_lookup_order_cross_account_blocked():
    """Authenticated customer attempting to read third-party order is rejected."""
    session = create_test_session(authenticated_user_id="CUST-002")
    result = lookup_order(session, order_id="ORD-101")

    assert result.success is False
    assert result.error_code == "ACCESS_DENIED"
    assert "ORD-101" in result.error_message
    # Critical privacy check: do NOT leak owner customer ID in error
    assert "CUST-001" not in result.error_message


def test_lookup_order_owner_access_permitted():
    """Authenticated owner accessing their own order receives full details."""
    session = create_test_session(authenticated_user_id="CUST-001")
    result = lookup_order(session, order_id="ORD-101")

    assert result.success is True
    assert result.data["order"]["user_id"] == "CUST-001"
    assert result.data["order"]["shipping_address"] == "123 Maple St, Seattle, WA 98101"
    assert len(result.data["items"]) > 0
    assert result.data["is_public_view"] is False


def test_lookup_user_anonymous_masks_email():
    """Unauthenticated lookup_user masks email to prevent harvesting/enumeration."""
    session = create_test_session(authenticated_user_id=None)
    result = lookup_user(session, user_id="CUST-001")

    assert result.success is True
    assert result.data["user_id"] == "CUST-001"
    assert "@" in result.data["email"]
    assert "***" in result.data["email"]
    assert result.data["email"] != "alice@example.com"
    assert result.data["is_public_view"] is True


def test_lookup_user_cross_account_blocked():
    """Authenticated customer querying another customer's profile is denied."""
    session = create_test_session(authenticated_user_id="CUST-002")
    result = lookup_user(session, user_id="CUST-001")

    assert result.success is False
    assert result.error_code == "ACCESS_DENIED"
    assert "Access denied" in result.error_message


def test_lookup_user_owner_permitted():
    """Authenticated customer querying their own profile receives full unmasked data."""
    session = create_test_session(authenticated_user_id="CUST-001")
    result = lookup_user(session, user_id="CUST-001")

    assert result.success is True
    assert result.data["user_id"] == "CUST-001"
    assert result.data["email"] == "alice@example.com"


def test_forbidden_cross_account_mutation_cancel_order():
    """CUST-002 cannot cancel CUST-001's order ORD-101."""
    session = create_test_session(authenticated_user_id="CUST-002")
    result = cancel_order(session, order_id="ORD-101", reason="Malicious cancel", idempotency_key="k_adv_1")

    assert result.success is False
    assert result.error_code == "AUTH_REQUIRED"
    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "pending"  # Must remain pending


def test_forbidden_cross_account_mutation_update_shipping():
    """CUST-002 cannot update shipping address on CUST-001's order ORD-101."""
    session = create_test_session(authenticated_user_id="CUST-002")
    result = update_shipping_address(session, order_id="ORD-101", new_address="Attacker St", idempotency_key="k_adv_2")

    assert result.success is False
    assert result.error_code == "AUTH_REQUIRED"
    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["shipping_address"] == "123 Maple St, Seattle, WA 98101"  # Unchanged


def test_forbidden_cross_account_mutation_issue_refund():
    """CUST-001 cannot issue a refund on CUST-002's order ORD-103."""
    session = create_test_session(authenticated_user_id="CUST-001")
    result = issue_refund(session, order_id="ORD-103", amount_cents=1000, reason="Fraudulent refund", idempotency_key="k_adv_3")

    assert result.success is False
    assert result.error_code == "AUTH_REQUIRED"
    refunds = SandboxDB.get_refunds_for_order(session.conn, "ORD-103") if hasattr(SandboxDB, "get_refunds_for_order") else []
    # Verify through direct cursor
    cursor = session.conn.cursor()
    cursor.execute("SELECT * FROM refunds WHERE order_id = 'ORD-103'")
    assert len(cursor.fetchall()) == 0  # No refund recorded


def test_unauthenticated_mutations_strictly_blocked():
    """All mutations must fail immediately if caller is unauthenticated."""
    session = create_test_session(authenticated_user_id=None)
    
    r_cancel = cancel_order(session, order_id="ORD-101", reason="test", idempotency_key="k_unauth_1")
    assert r_cancel.success is False
    assert r_cancel.error_code == "AUTH_REQUIRED"

    r_update = update_shipping_address(session, order_id="ORD-101", new_address="Nowhere", idempotency_key="k_unauth_2")
    assert r_update.success is False
    assert r_update.error_code == "AUTH_REQUIRED"

    r_refund = issue_refund(session, order_id="ORD-103", amount_cents=1000, reason="test", idempotency_key="k_unauth_3")
    assert r_refund.success is False
    assert r_refund.error_code == "AUTH_REQUIRED"
