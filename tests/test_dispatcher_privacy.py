"""
Tests for privacy and access control enforcement through the real dispatcher.

Verifies:
1. Anonymous lookup_order returns public status and masks PII.
2. Authenticated owner lookup_order returns complete details.
3. Authenticated cross-account lookup_order is rejected with ACCESS_DENIED.
4. Error messages do not leak third-party owner identities or existence clues.
5. Anonymous lookup_user masks email to prevent harvesting/enumeration.
6. Authenticated owner lookup_user returns complete unmasked profile.
7. Authenticated cross-user lookup_user is rejected with ACCESS_DENIED.
8. Real dispatcher dispatch_tool_call integration matches Stage 6 schema.
"""

import pytest
from runwise.agent.dispatcher import dispatch_tool_call
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext

FROZEN_CLOCK = "2026-10-15T12:00:00Z"


def create_session(authenticated_user_id: str | None = None) -> SessionContext:
    conn = SandboxDB.create_connection()
    session = SessionContext(
        conn=conn,
        trial_id="test_dispatcher_privacy",
        current_time_iso=FROZEN_CLOCK,
        authenticated_user_id=authenticated_user_id,
    )
    if authenticated_user_id:
        session.authorize_action("*", "*")
    return session


def test_dispatcher_anonymous_lookup_order_masks_pii():
    """Verify anonymous caller through dispatcher gets masked address and user_id."""
    session = create_session(authenticated_user_id=None)
    result = dispatch_tool_call(session, "lookup_order", {"order_id": "ORD-101"})

    assert result.success is True
    assert result.error_code is None
    data = result.data
    assert "order" in data
    order = data["order"]
    assert order["order_id"] == "ORD-101"
    assert order["status"] == "pending"
    assert order["user_id"] == "***"
    assert "Masked" in order["shipping_address"]
    assert "123 Maple St" not in order["shipping_address"]
    assert "items" not in data
    assert "refunds" not in data
    assert data["is_public_view"] is True


def test_dispatcher_owner_lookup_order_returns_full_details():
    """Verify authenticated owner through dispatcher gets full order details."""
    session = create_session(authenticated_user_id="CUST-001")
    result = dispatch_tool_call(session, "lookup_order", {"order_id": "ORD-101"})

    assert result.success is True
    assert result.error_code is None
    data = result.data
    assert "order" in data
    order = data["order"]
    assert order["order_id"] == "ORD-101"
    assert order["user_id"] == "CUST-001"
    assert order["shipping_address"] == "123 Maple St, Seattle, WA 98101"
    assert "items" in data
    assert len(data["items"]) == 2
    assert "refunds" in data
    assert data["is_public_view"] is False


def test_dispatcher_cross_account_lookup_order_denied_without_identity_leak():
    """Verify authenticated non-owner gets ACCESS_DENIED and owner ID is not leaked."""
    session = create_session(authenticated_user_id="CUST-002")
    result = dispatch_tool_call(session, "lookup_order", {"order_id": "ORD-101"})

    assert result.success is False
    assert result.error_code == "ACCESS_DENIED"
    assert "Access denied" in result.error_message
    assert "ORD-101" in result.error_message
    # Critical privacy check: owner identity 'CUST-001' must NOT appear in error message
    assert "CUST-001" not in result.error_message


def test_dispatcher_anonymous_lookup_user_masks_email():
    """Verify anonymous caller through dispatcher gets masked email."""
    session = create_session(authenticated_user_id=None)
    result = dispatch_tool_call(session, "lookup_user", {"user_id": "CUST-001"})

    assert result.success is True
    assert result.error_code is None
    data = result.data
    assert data["user_id"] == "CUST-001"
    assert data["username"] == "alice_smith"
    assert data["email"] == "a***@example.com"
    assert data["is_public_view"] is True


def test_dispatcher_owner_lookup_user_returns_full_profile():
    """Verify authenticated owner gets unmasked email."""
    session = create_session(authenticated_user_id="CUST-001")
    result = dispatch_tool_call(session, "lookup_user", {"user_id": "CUST-001"})

    assert result.success is True
    assert result.error_code is None
    data = result.data
    assert data["user_id"] == "CUST-001"
    assert data["email"] == "alice@example.com"


def test_dispatcher_cross_user_lookup_user_denied():
    """Verify authenticated non-owner gets ACCESS_DENIED on customer profile."""
    session = create_session(authenticated_user_id="CUST-002")
    result = dispatch_tool_call(session, "lookup_user", {"user_id": "CUST-001"})

    assert result.success is False
    assert result.error_code == "ACCESS_DENIED"
    assert "Access denied" in result.error_message


def test_dispatcher_json_string_invocation_with_privacy_controls():
    """Verify dispatcher safely parses LLM JSON strings and applies privacy controls."""
    session = create_session(authenticated_user_id="CUST-002")
    raw_args = '{"order_id": "ORD-101"}'
    result = dispatch_tool_call(session, "lookup_order", raw_args)

    assert result.success is False
    assert result.error_code == "ACCESS_DENIED"
