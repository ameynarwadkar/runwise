"""
Regression test suite for deterministic Action-Scope Guard.

Verifies:
1. Partial item cancellation is strictly blocked from executing whole-order cancellation.
2. Ambiguous cancellation scope is blocked from executing whole-order cancellation.
3. Explicit full-order cancellation is permitted when authorized and order is pending.
4. Idempotent retries with the same idempotency key succeed safely.
5. Duplicate/replay confirmation attempts are strictly prevented by single-use token consumption.
6. Mismatched confirmation order or scope is rejected.
7. Dispatcher integration respects action-scope restrictions.
"""

from __future__ import annotations

import pytest
from runwise.agent.dispatcher import dispatch_tool_call
from runwise.domain.authorization import (
    ActionScope,
    ActionStatus,
    PendingAction,
    classify_request_intent,
)
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext
from runwise.domain.tools import cancel_order, verify_customer

FROZEN_CLOCK = "2026-10-15T12:00:00Z"


@pytest.fixture
def session() -> SessionContext:
    conn = SandboxDB.create_connection()
    ctx = SessionContext(
        conn=conn,
        trial_id="test_action_scope_trial",
        current_time_iso=FROZEN_CLOCK,
        authenticated_user_id="CUST-001",
    )
    ctx.authorize_action("*", "*")
    yield ctx
    conn.close()


# ============================================================================
# 1. INTENT CLASSIFICATION: PARTIAL & AMBIGUOUS SCOPE DETECTION
# ============================================================================

def test_intent_classification_detects_partial_cancellation():
    """Verify that requests targeting specific items are classified as PARTIAL_ITEM."""
    prompt = "In order ORD-101 I bought a keyboard and a mouse. Please cancel only the mouse and leave the keyboard."
    intent = classify_request_intent(prompt)

    assert intent.action_scope == ActionScope.PARTIAL_ITEM
    assert intent.is_explicit_transaction is False
    assert len(intent.authorized_actions) == 0
    assert "partial item cancellation" in intent.reason.lower()


def test_intent_classification_detects_ambiguous_cancellation_scope():
    """Verify that vague/ambiguous partial cancellation requests are classified as AMBIGUOUS."""
    prompt = "I need to cancel part of my order ORD-101. What can I do?"
    intent = classify_request_intent(prompt)

    assert intent.action_scope == ActionScope.AMBIGUOUS
    assert intent.is_explicit_transaction is False
    assert len(intent.authorized_actions) == 0


def test_intent_classification_full_cancellation_authorized():
    """Verify that explicit whole-order cancellation is classified as FULL_ORDER and authorized."""
    prompt = "Oscar Isaac (CUST-001, PIN 1234). I placed order ORD-101 by mistake. Since it is still pending, cancel it immediately please."
    intent = classify_request_intent(prompt)

    assert intent.action_scope == ActionScope.FULL_ORDER
    assert intent.is_explicit_transaction is True
    assert ("cancel_order", "ORD-101") in intent.authorized_actions


# ============================================================================
# 2. DETERMINISTIC ACTION-SCOPE GUARD ENFORCEMENT
# ============================================================================

def test_action_scope_guard_blocks_whole_order_cancellation_on_partial_request(session: SessionContext):
    """
    CRITICAL SAFETY GATE: A user's request to cancel one item must never authorize
    whole-order cancellation.
    """
    # Simulate server setting trusted action scope from user prompt
    prompt = "Please cancel only the mouse from ORD-101 and keep the monitor."
    intent = classify_request_intent(prompt)
    session.set_action_scope("cancel_order", "ORD-101", intent.action_scope)

    # Even if authenticated, cancel_order must be deterministically blocked
    result = cancel_order(session, order_id="ORD-101", reason="cancel mouse only", idempotency_key="k_scope_1")

    assert result.success is False
    assert result.error_code == "ACTION_SCOPE_MISMATCH"
    assert "restricted to PARTIAL_ITEM" in result.error_message

    # Order in database must remain pending!
    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "pending"


def test_action_scope_guard_blocks_ambiguous_scope_cancellation(session: SessionContext):
    """Ambiguous cancellation scope must never execute full-order cancellation."""
    session.set_action_scope("cancel_order", "ORD-101", ActionScope.AMBIGUOUS)

    result = cancel_order(session, order_id="ORD-101", reason="cancel part of order", idempotency_key="k_scope_2")

    assert result.success is False
    assert result.error_code == "ACTION_SCOPE_MISMATCH"
    assert "restricted to AMBIGUOUS" in result.error_message

    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "pending"


def test_action_scope_guard_permits_authorized_full_cancellation(session: SessionContext):
    """Explicit authorized full-order cancellation must execute successfully."""
    session.authorize_action("cancel_order", "ORD-101")

    result = cancel_order(session, order_id="ORD-101", reason="accidental purchase", idempotency_key="k_scope_3")

    assert result.success is True
    assert result.data["order_id"] == "ORD-101"
    assert result.data["status"] == "cancelled"

    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "cancelled"


# ============================================================================
# 3. RETRIES, DUPLICATE CALLS & CONFIRMATION INTEGRITY
# ============================================================================

def test_idempotent_retry_returns_safe_success(session: SessionContext):
    """Calling cancel_order again with the same idempotency key succeeds safely without re-cancelling."""
    session.authorize_action("cancel_order", "ORD-101")

    # First call
    r1 = cancel_order(session, order_id="ORD-101", reason="initial cancel", idempotency_key="k_retry_1")
    assert r1.success is True

    # Retry call
    r2 = cancel_order(session, order_id="ORD-101", reason="retry cancel", idempotency_key="k_retry_1")
    assert r2.success is True
    assert r2.data["status"] == "cancelled"


def test_duplicate_confirmation_token_consumption_prevented(session: SessionContext):
    """Replaying a confirmation token twice raises a replay error."""
    action = PendingAction(
        action_id="act_test_replay",
        action_type="cancel_order",
        order_id="ORD-101",
        customer_id="CUST-001",
        scope=ActionScope.FULL_ORDER,
    )
    token = action.confirmation_token
    session.stage_pending_action(action)

    # First confirmation succeeds
    confirmed = session.confirm_pending_action(action.action_id, token, expected_order_id="ORD-101")
    assert confirmed is True

    # Mark as executed / consumed
    session.consumed_action_tokens.add(token)
    action.status = ActionStatus.EXECUTED

    # Duplicate confirmation attempt must be rejected
    with pytest.raises(ValueError, match="already been executed/consumed"):
        session.confirm_pending_action(action.action_id, token, expected_order_id="ORD-101")


def test_mismatched_confirmation_scope_rejected(session: SessionContext):
    """Confirming an action with a mismatched scope raises a ValueError."""
    action = PendingAction(
        action_id="act_test_mismatch",
        action_type="cancel_order",
        order_id="ORD-101",
        customer_id="CUST-001",
        scope=ActionScope.PARTIAL_ITEM,
    )
    token = action.confirmation_token
    session.stage_pending_action(action)

    # Attempting to confirm with expected_scope=FULL_ORDER must fail
    with pytest.raises(ValueError, match="Confirmation scope mismatch"):
        session.confirm_pending_action(
            action.action_id,
            token,
            expected_order_id="ORD-101",
            expected_scope=ActionScope.FULL_ORDER,
        )


def test_dispatcher_enforces_action_scope_guard(session: SessionContext):
    """Verifies that dispatch_tool_call blocks whole-order cancellation when scope is partial."""
    session.set_action_scope("cancel_order", "ORD-101", ActionScope.PARTIAL_ITEM)

    result = dispatch_tool_call(
        session,
        "cancel_order",
        {"order_id": "ORD-101", "reason": "cancel mouse", "idempotency_key": "k_disp_1"},
    )

    assert result.success is False
    assert result.error_code == "ACTION_SCOPE_MISMATCH"


# ============================================================================
# 4. ADVERSARIAL FAIL-CLOSED SECURITY GATES (PRIORITY 0)
# ============================================================================

def test_adversarial_missing_action_scope_fails_closed(session: SessionContext):
    """
    PRIORITY 0 GATE: An absent or unset action scope must strictly block full-order
    cancellation. None must never bypass the guard.
    """
    session.action_scopes.clear()
    assert session.get_action_scope("cancel_order", "ORD-101") is None

    result = cancel_order(
        session,
        order_id="ORD-101",
        reason="Attacker probing missing scope",
        idempotency_key="k_adv_missing_1",
    )

    assert result.success is False
    assert result.error_code == "ACTION_SCOPE_MISMATCH"
    assert "UNSET/ABSENT" in result.error_message

    # DB state must remain pending
    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "pending"

    # Audit log must catch the blocked mutation
    logs = SandboxDB.get_audit_log(session.conn, trial_id=session.trial_id)
    assert any(
        log["event_type"] == "MUTATION_BLOCKED" and log["status_code"] == "ACTION_SCOPE_MISMATCH"
        for log in logs
    )


def test_adversarial_empty_session_state_fails_closed():
    """
    PRIORITY 0 GATE: A fresh, empty SessionContext with no authentication or scope
    must fail closed without mutating the database.
    """
    conn = SandboxDB.create_connection()
    empty_session = SessionContext(
        conn=conn,
        trial_id="test_trial_empty_state",
        current_time_iso=FROZEN_CLOCK,
    )

    result = cancel_order(
        empty_session,
        order_id="ORD-101",
        reason="Direct unauthenticated call",
        idempotency_key="k_adv_empty_1",
    )

    assert result.success is False
    assert result.error_code == "AUTH_REQUIRED"

    order = SandboxDB.get_order(conn, "ORD-101")
    assert order["status"] == "pending"
    conn.close()


def test_adversarial_scope_overwrite_prevented(session: SessionContext):
    """
    PRIORITY 0 GATE: A session restricted to PARTIAL_ITEM cannot be overwritten
    to FULL_ORDER by subsequent unconfirmed or ambiguous input.
    """
    session.set_action_scope("cancel_order", "ORD-101", ActionScope.PARTIAL_ITEM)

    # Attempt unauthorized downgrade/overwrite
    session.set_action_scope("cancel_order", "ORD-101", ActionScope.FULL_ORDER, force=False)

    # Scope must remain PARTIAL_ITEM
    assert session.get_action_scope("cancel_order", "ORD-101") == ActionScope.PARTIAL_ITEM

    # cancel_order must remain blocked
    result = cancel_order(
        session,
        order_id="ORD-101",
        reason="Attempting to cancel after failed overwrite",
        idempotency_key="k_adv_overwrite_1",
    )
    assert result.success is False
    assert result.error_code == "ACTION_SCOPE_MISMATCH"

    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "pending"


def test_adversarial_stale_confirmation_replay_prevented(session: SessionContext):
    """
    PRIORITY 0 GATE: Stale or consumed confirmations cannot be replayed to execute
    a second mutation or authorize another order.
    """
    action = PendingAction(
        action_id="act_stale_replay_01",
        action_type="cancel_order",
        order_id="ORD-101",
        customer_id="CUST-001",
        scope=ActionScope.FULL_ORDER,
    )
    token = action.confirmation_token
    session.stage_pending_action(action)

    session.confirm_pending_action(action.action_id, token, expected_order_id="ORD-101")
    result = cancel_order(session, order_id="ORD-101", reason="Authorized cancel", idempotency_key="k_stale_1")
    assert result.success is True

    # Token is now consumed
    assert token in session.consumed_action_tokens

    # Attempt to confirm or fetch action again must fail
    with pytest.raises(ValueError, match="already been executed/consumed"):
        session.confirm_pending_action(action.action_id, token, expected_order_id="ORD-101")

    assert session.get_confirmed_action("cancel_order", "ORD-101") is None


def test_adversarial_cross_account_scope_and_confirmation_reuse_blocked(session: SessionContext):
    """
    PRIORITY 0 GATE: Scopes or pending actions created for customer A cannot be
    confirmed or executed by customer B.
    """
    # Action created for CUST-001 on ORD-101
    action = PendingAction(
        action_id="act_cross_account_01",
        action_type="cancel_order",
        order_id="ORD-101",
        customer_id="CUST-001",
        scope=ActionScope.FULL_ORDER,
    )
    token = action.confirmation_token
    session.stage_pending_action(action)

    # Attacker authenticated as CUST-002 attempts to confirm CUST-001's action
    session.authenticated_user_id = "CUST-002"
    with pytest.raises(ValueError, match="Confirmation customer mismatch"):
        session.confirm_pending_action(
            action.action_id,
            token,
            expected_order_id="ORD-101",
            expected_customer_id="CUST-002",
        )

    # CUST-002 attempts to execute cancel_order on ORD-101 (owned by CUST-001)
    result = cancel_order(
        session,
        order_id="ORD-101",
        reason="Malicious cross-account cancellation",
        idempotency_key="k_cross_cancel_1",
    )
    assert result.success is False
    assert result.error_code == "AUTH_REQUIRED"

    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "pending"


def test_adversarial_direct_dispatcher_bypass_blocked(session: SessionContext):
    """
    PRIORITY 0 GATE: Attacker injecting LLM tool-call arguments with rogue parameters
    (e.g. scope='FULL_ORDER', authorized=True) cannot bypass server authorization.
    """
    session.action_scopes.clear()

    # Attempt 1: Extra parameters in dispatcher call
    res1 = dispatch_tool_call(
        session,
        "cancel_order",
        {
            "order_id": "ORD-101",
            "reason": "Bypass attempt",
            "scope": "FULL_ORDER",
            "authorized": True,
            "idempotency_key": "k_disp_rogue_1",
        },
    )
    # Python catches unrecognized kwargs as ARGUMENT_MISMATCH
    assert res1.success is False
    assert res1.error_code == "ARGUMENT_MISMATCH"

    # Attempt 2: Standard parameters without server-set scope
    res2 = dispatch_tool_call(
        session,
        "cancel_order",
        {"order_id": "ORD-101", "reason": "Bypass attempt 2", "idempotency_key": "k_disp_rogue_2"},
    )
    assert res2.success is False
    assert res2.error_code == "ACTION_SCOPE_MISMATCH"

    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "pending"


def test_adversarial_contradictory_request_fails_closed(session: SessionContext):
    """
    PRIORITY 0 GATE: Contradictory customer request containing negation ("do not cancel")
    must fail closed to INFORMATIONAL_INQUIRY and block whole-order cancellation.
    """
    prompt = "Please cancel order ORD-101 right now, but wait, actually do not cancel or refund anything!"
    intent = classify_request_intent(prompt)

    assert intent.is_explicit_transaction is False
    assert intent.intent_type == "INFORMATIONAL_INQUIRY"
    assert len(intent.authorized_actions) == 0

    session.set_action_scope("cancel_order", "ORD-101", intent.action_scope)

    res = dispatch_tool_call(
        session,
        "cancel_order",
        {"order_id": "ORD-101", "reason": "contradictory prompt", "idempotency_key": "k_contra_1"},
    )
    assert res.success is False
    # Scope was unset/informational -> blocked
    assert res.error_code in ("ACTION_SCOPE_MISMATCH", "CONFIRMATION_REQUIRED")

    order = SandboxDB.get_order(session.conn, "ORD-101")
    assert order["status"] == "pending"
