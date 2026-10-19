"""
Unit and regression tests for trusted, server-controlled financial action authorization.

Verifies:
1. Damaged package inquiry without refund authorization creates PendingAction and blocks mutation.
2. Empty package inquiry without refund authorization blocks mutation.
3. Explicit refund request executes directly without requiring interactive confirmation.
4. Incorrect or missing confirmation token is rejected.
5. Confirmation for a different amount or order is rejected.
6. Replayed confirmation is prevented from executing twice.
7. Existing legitimate mutation workflows continue to execute correctly.
"""

from __future__ import annotations

import pytest

from runwise.agent.dispatcher import dispatch_tool_call
from runwise.domain.authorization import (
    ActionStatus,
    classify_request_intent,
)
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext
from runwise.domain.tools import cancel_order, issue_refund, verify_customer


@pytest.fixture
def session() -> SessionContext:
    """Provides an isolated in-memory SQLite sandbox with deterministic simulation clock."""
    conn = SandboxDB.create_connection()
    ctx = SessionContext(
        conn=conn,
        trial_id="test_financial_auth_trial",
        current_time_iso="2026-10-15T12:00:00Z",
    )
    yield ctx
    conn.close()


# ============================================================================
# 1. INTENT CLASSIFICATION TESTS
# ============================================================================

def test_intent_classification_distinguishes_inquiries_from_explicit_commands() -> None:
    # A. Ambiguous / Informational Inquiries
    inq1 = classify_request_intent("The package for ORD-103 arrived empty. What can you do for me? Customer: CUST-002, code: 1234.")
    assert inq1.is_explicit_transaction is False
    assert inq1.intent_type == "INFORMATIONAL_INQUIRY"
    assert len(inq1.authorized_actions) == 0

    inq2 = classify_request_intent("My delivered items on ORD-103 were damaged. How do you handle this? CUST-002, code: 1234.")
    assert inq2.is_explicit_transaction is False
    assert inq2.intent_type == "INFORMATIONAL_INQUIRY"

    inq3 = classify_request_intent("What items, unit prices, and quantities are listed in order ORD-101?")
    assert inq3.is_explicit_transaction is False

    # B. Negation Financial Inquiries
    neg1 = classify_request_intent("I do not want a refund, I just need a breakdown of why order ORD-102 was charged $50.")
    assert neg1.is_explicit_transaction is False
    assert neg1.intent_type == "INFORMATIONAL_INQUIRY"

    neg2 = classify_request_intent("Please do not refund ORD-102; clarify why my statement shows an extra line item fee.")
    assert neg2.is_explicit_transaction is False

    # C. Explicit Transaction Commands
    exp1 = classify_request_intent("Please issue a $50 refund for my delivered order ORD-103. Customer: CUST-002, PIN: 1234.")
    assert exp1.is_explicit_transaction is True
    assert exp1.intent_type == "EXPLICIT_TRANSACTION"
    assert ("issue_refund", "ORD-103") in exp1.authorized_actions

    exp2 = classify_request_intent("Please cancel my pending order ORD-101 right now.")
    assert exp2.is_explicit_transaction is True
    assert ("cancel_order", "ORD-101") in exp2.authorized_actions

    exp3 = classify_request_intent("Refund my order ORD-104 immediately, it is defective.")
    assert exp3.is_explicit_transaction is True
    assert ("issue_refund", "ORD-104") in exp3.authorized_actions


# ============================================================================
# 2. REGRESSION TESTS: INQUIRIES WITHOUT REFUND AUTHORIZATION
# ============================================================================

def test_damaged_package_inquiry_without_authorization_creates_pending_action(session: SessionContext) -> None:
    """
    Regression Test 1: Customer asks about damaged items on ORD-103.
    The agent must not mutate the database; a PendingAction must be created with CONFIRMATION_REQUIRED.
    """
    # Authenticate customer CUST-002
    v_res = verify_customer(session, "CUST-002", "1234")
    assert v_res.success is True

    # Prompt is an informational inquiry (no explicit refund authorization granted)
    intent = classify_request_intent("My delivered items on ORD-103 were damaged. How do you handle this? CUST-002, code: 1234.")
    assert intent.is_explicit_transaction is False
    # Notice: session.authorized_explicit_actions remains empty!

    # Model attempts to call issue_refund
    res = issue_refund(
        session,
        order_id="ORD-103",
        amount_cents=7500,
        reason="Damaged items",
        idempotency_key="idemp_dmg_01",
    )

    # Must be blocked with CONFIRMATION_REQUIRED
    assert res.success is False
    assert res.error_code == "CONFIRMATION_REQUIRED"
    assert "requires explicit customer confirmation" in res.error_message
    assert res.data is not None
    assert res.data["status"] == "PENDING"
    assert res.data["order_id"] == "ORD-103"
    assert res.data["amount_cents"] == 7500

    # Verify pending action recorded on session
    action_id = res.data["action_id"]
    assert action_id in session.pending_actions
    pending = session.pending_actions[action_id]
    assert pending.status == ActionStatus.PENDING
    assert pending.amount_cents == 7500
    assert pending.customer_id == "CUST-002"
    assert pending.policy_snapshot["status"] == "delivered"

    # Invariant: Database state must be completely untouched
    cursor = session.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM refunds WHERE order_id = 'ORD-103'")
    assert cursor.fetchone()[0] == 0


def test_empty_package_inquiry_without_authorization_blocks_mutation(session: SessionContext) -> None:
    """
    Regression Test 2: Customer asks about empty package on ORD-103.
    Mutation is blocked with CONFIRMATION_REQUIRED and DB has 0 refunds.
    """
    verify_customer(session, "CUST-002", "1234")

    res = issue_refund(
        session,
        order_id="ORD-103",
        amount_cents=7500,
        reason="Package arrived empty",
        idempotency_key="idemp_empty_01",
    )

    assert res.success is False
    assert res.error_code == "CONFIRMATION_REQUIRED"

    cursor = session.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM refunds WHERE order_id = 'ORD-103'")
    assert cursor.fetchone()[0] == 0


# ============================================================================
# 3. REGRESSION TESTS: EXPLICIT REFUND REQUEST
# ============================================================================

def test_explicit_refund_request_executes_without_interactive_confirmation(session: SessionContext) -> None:
    """
    Regression Test 3: Customer explicitly commands a refund on ORD-103.
    Explicit authorization allows direct execution.
    """
    verify_customer(session, "CUST-002", "1234")

    # Trusted application registers explicit transaction directive
    intent = classify_request_intent("Please issue a $50 refund for my delivered order ORD-103. Customer: CUST-002, PIN: 1234.")
    assert intent.is_explicit_transaction is True
    for act_type, oid in intent.authorized_actions:
        session.authorize_action(act_type, oid)

    res = issue_refund(
        session,
        order_id="ORD-103",
        amount_cents=5000,
        reason="Customer requested $50 refund",
        idempotency_key="idemp_exp_refund_01",
    )

    assert res.success is True
    assert res.data is not None
    assert res.data["status"] == "approved"
    assert res.data["amount_cents"] == 5000

    cursor = session.conn.cursor()
    cursor.execute("SELECT amount_cents, status FROM refunds WHERE order_id = 'ORD-103'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 5000
    assert row[1] == "approved"


# ============================================================================
# 4. REGRESSION TESTS: INCORRECT OR MISSING CONFIRMATION
# ============================================================================

def test_incorrect_or_missing_confirmation_token_is_rejected(session: SessionContext) -> None:
    """
    Regression Test 4: Staged action cannot be confirmed with an invalid token.
    """
    verify_customer(session, "CUST-002", "1234")

    # Stage an action via initial inquiry call
    res = issue_refund(session, "ORD-103", 7500, "Inquiry", "idemp_tok_01")
    action_id = res.data["action_id"]
    pending = session.pending_actions[action_id]

    # Non-existent action ID
    with pytest.raises(ValueError, match="Action 'act_fake' not found"):
        session.confirm_pending_action("act_fake", pending.confirmation_token)

    # Wrong token
    with pytest.raises(ValueError, match="Invalid confirmation token"):
        session.confirm_pending_action(action_id, "wrong_token_xyz")

    # Action remains PENDING and cannot execute
    assert pending.status == ActionStatus.PENDING
    assert session.get_confirmed_action("issue_refund", "ORD-103", 7500) is None


# ============================================================================
# 5. REGRESSION TESTS: CONFIRMATION MISMATCH (DIFFERENT AMOUNT OR ORDER)
# ============================================================================

def test_confirmation_bound_to_exact_order_and_amount(session: SessionContext) -> None:
    """
    Regression Test 5: Confirming an action binds strictly to the exact order and amount.
    """
    verify_customer(session, "CUST-002", "1234")

    res = issue_refund(session, "ORD-103", 7500, "Damaged", "idemp_bind_01")
    action_id = res.data["action_id"]
    token = session.pending_actions[action_id].confirmation_token

    # Order mismatch
    with pytest.raises(ValueError, match="Confirmation order mismatch: expected ORD-101, got ORD-103"):
        session.confirm_pending_action(action_id, token, expected_order_id="ORD-101")

    # Amount mismatch
    with pytest.raises(ValueError, match="Confirmation amount mismatch: expected 5000, got 7500"):
        session.confirm_pending_action(action_id, token, expected_amount_cents=5000)

    # Correct confirmation succeeds
    ok = session.confirm_pending_action(action_id, token, expected_order_id="ORD-103", expected_amount_cents=7500)
    assert ok is True
    assert session.pending_actions[action_id].status == ActionStatus.CONFIRMED


# ============================================================================
# 6. REGRESSION TESTS: REPLAYED CONFIRMATION PREVENTION
# ============================================================================

def test_replayed_confirmation_is_prevented_from_executing_twice(session: SessionContext) -> None:
    """
    Regression Test 6: A confirmed action can only be executed once. Subsequent replay attempts fail.
    """
    verify_customer(session, "CUST-002", "1234")

    # 1. Stage and confirm action
    res = issue_refund(session, "ORD-103", 3000, "Package empty", "idemp_replay_01")
    action_id = res.data["action_id"]
    token = session.pending_actions[action_id].confirmation_token
    session.confirm_pending_action(action_id, token, expected_order_id="ORD-103", expected_amount_cents=3000)

    # 2. Execute refund using confirmed action (with a fresh idempotency key to test replay)
    exec_res = issue_refund(session, "ORD-103", 3000, "Package empty", "idemp_replay_exec_1")
    assert exec_res.success is True
    assert exec_res.data["status"] == "approved"

    # Action is now EXECUTED and token is consumed
    assert session.pending_actions[action_id].status == ActionStatus.EXECUTED
    assert token in session.consumed_action_tokens

    # 3. Re-confirming already consumed action raises error
    with pytest.raises(ValueError, match="already been executed/consumed"):
        session.confirm_pending_action(action_id, token)

    # 4. Attempting another mutation without a new confirmation is blocked
    replay_res = issue_refund(session, "ORD-103", 3000, "Package empty re-attempt", "idemp_replay_exec_2")
    assert replay_res.success is False
    assert replay_res.error_code == "CONFIRMATION_REQUIRED"

    # Total refunds in DB must still be exactly 1
    cursor = session.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM refunds WHERE order_id = 'ORD-103'")
    assert cursor.fetchone()[0] == 1


# ============================================================================
# 7. REGRESSION TESTS: EXISTING SUCCESSFUL MUTATION WORKFLOWS
# ============================================================================

def test_existing_cancellation_workflow_preserves_compatibility(session: SessionContext) -> None:
    """
    Regression Test 7: Standard pending order cancellation continues to work.
    """
    verify_customer(session, "CUST-001", "1234")

    # User explicitly requested cancellation
    intent = classify_request_intent("Please cancel my pending order ORD-101 right now.")
    assert intent.is_explicit_transaction is True
    session.authorize_action("cancel_order", "ORD-101")

    res = cancel_order(session, "ORD-101", "Changed mind", "idemp_cancel_01")
    assert res.success is True
    assert res.data["status"] == "cancelled"

    cursor = session.conn.cursor()
    cursor.execute("SELECT status FROM orders WHERE order_id = 'ORD-101'")
    assert cursor.fetchone()[0] == "cancelled"


def test_dispatcher_safely_handles_confirmation_flow(session: SessionContext) -> None:
    """
    Regression Test 8: Dispatcher routes tool calls through the authorization boundary.
    """
    verify_customer(session, "CUST-002", "1234")

    # Informational context -> dispatch issue_refund -> returns CONFIRMATION_REQUIRED
    res = dispatch_tool_call(
        session,
        tool_name="issue_refund",
        arguments={"order_id": "ORD-103", "amount_cents": 7500, "reason": "Damaged", "idempotency_key": "disp_01"},
    )
    assert res.success is False
    assert res.error_code == "CONFIRMATION_REQUIRED"
    assert "action_id" in res.data


def test_agent_loop_deliberate_rogue_mutation_blocked_by_domain_boundary() -> None:
    """
    Regression Test 9 (Offline Integration Test):
    Deliberately forces the LLM / Dispatcher to invoke issue_refund on an informational inquiry.
    Verifies that:
    1. AgentLoop classifies prompt as INFORMATIONAL_INQUIRY and grants NO explicit authorization.
    2. Model deliberately emits tool call for issue_refund(ORD-103, 7500).
    3. The domain layer blocks execution, records MUTATION_BLOCKED, and returns CONFIRMATION_REQUIRED.
    4. A PendingAction is staged on the session.
    5. Database state is completely untouched (0 refunds for ORD-103).
    6. Model receives the rejection in turn history and explains confirmation options without mutating.
    """
    from types import SimpleNamespace
    from runwise.agent.loop import AgentLoop, ExitReason

    conn = SandboxDB.create_connection()
    session = SessionContext(
        conn=conn,
        trial_id="test_deliberate_rogue_trial",
        current_time_iso="2026-10-15T12:00:00Z",
    )

    user_prompt = "My delivered items on ORD-103 were damaged. How do you handle this? CUST-002, code: 1234."

    def make_tool_call(call_id: str, name: str, args: dict) -> SimpleNamespace:
        func = SimpleNamespace(name=name, arguments=args)
        return SimpleNamespace(id=call_id, function=func)

    def make_mock_response(content: str | None = None, tool_calls: list | None = None) -> SimpleNamespace:
        msg = SimpleNamespace(content=content, tool_calls=tool_calls)
        choice = SimpleNamespace(message=msg)
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50)
        return SimpleNamespace(choices=[choice], usage=usage)

    # Step 1: Model verifies customer
    call1 = make_tool_call("tc_auth", "verify_customer", {"user_id": "CUST-002", "verification_code": "1234"})
    resp1 = make_mock_response(content=None, tool_calls=[call1])

    # Step 2: Model DELIBERATELY / ROGUELY invokes issue_refund without authorization
    call2 = make_tool_call("tc_rogue_refund", "issue_refund", {
        "order_id": "ORD-103",
        "amount_cents": 7500,
        "reason": "Damaged items",
        "idempotency_key": "idemp_rogue_999",
    })
    resp2 = make_mock_response(content=None, tool_calls=[call2])

    # Step 3: Model receives CONFIRMATION_REQUIRED and yields text
    resp3 = make_mock_response(content="Your order is eligible for a $75.00 refund. Would you like me to confirm and process it?")

    agent = AgentLoop(max_steps=5)
    trajectory = agent.run(
        user_prompt=user_prompt,
        session=session,
        mock_completions=[resp1, resp2, resp3],
    )

    # 1. Normal completion exit
    assert trajectory.exit_reason == ExitReason.NORMAL_COMPLETION

    # 2. Inspect events: tool call for issue_refund was intercepted and returned CONFIRMATION_REQUIRED
    refund_result_event = next(e for e in trajectory.events if e.event_type == "TOOL_RESULT" and "issue_refund" in e.content)
    assert refund_result_event.tool_result is not None
    assert refund_result_event.tool_result["success"] is False
    assert refund_result_event.tool_result["error_code"] == "CONFIRMATION_REQUIRED"

    # 3. PendingAction staged on session
    action_id = refund_result_event.tool_result["data"]["action_id"]
    assert action_id in session.pending_actions
    assert session.pending_actions[action_id].status == ActionStatus.PENDING

    # 4. Invariant: Database completely unchanged (0 refunds)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM refunds WHERE order_id = 'ORD-103'")
    assert cursor.fetchone()[0] == 0

    # 5. Audit log captured MUTATION_BLOCKED
    cursor.execute("SELECT status_code, tool_name FROM audit_log WHERE event_type = 'MUTATION_BLOCKED'")
    blocked_audit = cursor.fetchone()
    assert blocked_audit is not None
    assert blocked_audit[0] == "CONFIRMATION_REQUIRED"
    assert blocked_audit[1] == "issue_refund"

    conn.close()

