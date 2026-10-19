"""
Stage 6B Targeted Curriculum Generator:
Builds and validates 14 new, sandbox-grounded atomic decision points:
- 4 cross-account immediate refusals (addressing dev3_15 zero probing requirement)
- 4 partial line-item cancellation refusals / clarifications (addressing dev3_16 action-scope requirement)
- 3 grounded post-mutation confirmations
- 3 grounded explanations following executor denials

Total dataset size after merge: 196 decision points.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from runwise.agent.dispatcher import TOOL_SCHEMAS, dispatch_tool_call
from runwise.domain.authorization import ActionScope
from runwise.domain.model import SessionContext, ToolResult
from runwise.domain.tools import (
    cancel_order,
    issue_refund,
    update_shipping_address,
)

FROZEN_CLOCK = "2026-10-15T12:00:00Z"
SYSTEM_PROMPT = (
    "You are the official Customer Support AI for our e-commerce platform.\n"
    "Your goal is to assist customers accurately, politely, and strictly within company policy.\n\n"
    "CURRENT CONTEXT:\n"
    "- Current Time: 2026-10-15T12:00:00Z"
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "runwise" / "domain" / "schema.sql"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sft"


def make_sandbox(users=None, orders=None, items=None, refunds=None) -> tuple[sqlite3.Connection, SessionContext]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    if users:
        for u in users:
            conn.execute(
                "INSERT INTO users (user_id, username, email, password, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (u["user_id"], u["username"], u["email"], u.get("password", "1234"), u.get("status", "active"), 1720000000, 1720000000),
            )
    if orders:
        for o in orders:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username, email, password, status, created_at, updated_at) "
                "VALUES (?, ?, ?, '1234', 'active', 1720000000, 1720000000)",
                (o["user_id"], f"user_{o['user_id'].lower()}", f"{o['user_id'].lower()}@example.org"),
            )
            conn.execute(
                "INSERT INTO orders (order_id, created_at, user_id, status, shipping_address, total_amount_cents, delivered_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (o["order_id"], o.get("created_at", 1728000000), o["user_id"], o["status"], o["shipping_address"], o["total_amount_cents"], o.get("delivered_at")),
            )
    if items:
        for it in items:
            conn.execute(
                "INSERT INTO order_items (order_item_id, created_at, order_id, product_id, product_name, unit_price_cents, quantity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (it["order_item_id"], 1728000000, it["order_id"], it.get("product_id", "PROD-GEN"), it["product_name"], it["unit_price_cents"], it.get("quantity", 1)),
            )
    if refunds:
        for rf in refunds:
            conn.execute(
                "INSERT INTO refunds (refund_id, order_id, amount_cents, reason, status, idempotency_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rf["refund_id"], rf["order_id"], rf["amount_cents"], rf["reason"], rf.get("status", "approved"), rf.get("idempotency_key", f"idemp_{rf['refund_id']}"), 1728100000),
            )
    conn.commit()

    session = SessionContext(
        conn=conn,
        trial_id=f"trial_{uuid.uuid4().hex[:8]}",
        current_time_iso=FROZEN_CLOCK,
    )
    return conn, session


def tool_result_to_message(tool_call_id: str, tool_name: str, result: ToolResult) -> dict[str, Any]:
    content_obj = {
        "success": result.success,
        "error_code": result.error_code,
        "data": result.data,
        "error_message": result.error_message,
    }
    return {
        "role": "tool",
        "name": tool_name,
        "tool_call_id": tool_call_id,
        "content": json.dumps(content_obj, ensure_ascii=False),
        "tool_calls": None,
    }


def make_tool_call_turn(tool_name: str, arguments: dict[str, Any], call_id: str | None = None) -> dict[str, Any]:
    cid = call_id or f"call_{uuid.uuid4().hex[:8]}"
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": cid,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }
        ],
        "tool_call_id": None,
        "name": None,
    }


def make_dialogue_turn(content: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": None,
        "tool_call_id": None,
        "name": None,
    }


def make_user_turn(content: str) -> dict[str, Any]:
    return {
        "role": "user",
        "content": content,
        "tool_calls": None,
        "tool_call_id": None,
        "name": None,
    }


def serialize_dp(
    dp_id: str,
    domain: str,
    difficulty: str,
    customer_id: str | None,
    order_id: str | None,
    step_index: int,
    total_steps: int,
    decision_type: str,
    messages: list[dict[str, Any]],
    target_turn: dict[str, Any],
    target_tool_names: list[str],
) -> dict[str, Any]:
    all_msgs = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
            "tool_calls": None,
            "tool_call_id": None,
            "name": None,
        }
    ] + messages

    return {
        "decision_point_id": dp_id,
        "parent_example_id": dp_id.rsplit("_dp", 1)[0] if "_dp" in dp_id else dp_id,
        "curriculum_domain": domain,
        "difficulty": difficulty,
        "customer_id": customer_id,
        "order_id": order_id,
        "step_index": step_index,
        "total_steps_in_trajectory": total_steps,
        "decision_type": decision_type,
        "tools": TOOL_SCHEMAS,
        "messages": all_msgs,
        "target_turn": target_turn,
        "metadata": {
            "is_terminal": target_turn.get("content") is not None,
            "target_tool_names": target_tool_names,
        },
    }


def build_14_decision_points() -> list[dict[str, Any]]:
    dps = []

    # =========================================================================
    # CATEGORY 1: 4 CROSS-ACCOUNT IMMEDIATE REFUSALS (ZERO PROBING)
    # Target: Refuse third-party lookup / mutation in dialogue without tool calls.
    # =========================================================================

    # 1. Marcus Aurelius (CUST-851) asks for partner's order ORD-911
    prompt_c1 = (
        "Marcus Aurelius here (CUST-851, code 1234). I'd like to check the delivery address "
        "and shipment status for order ORD-911. My business partner asked me to look into it for him."
    )
    resp_c1 = (
        "I cannot access or share details for order ORD-911. Customer orders and shipping addresses "
        "are strictly confidential and can only be accessed by the verified account owner. "
        "Your partner will need to log in to their account to check this order."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_cross_001",
            domain="D9_cross_account_privacy",
            difficulty="hard",
            customer_id="CUST-851",
            order_id="ORD-911",
            step_index=1,
            total_steps=1,
            decision_type="security_refusal",
            messages=[make_user_turn(prompt_c1), make_dialogue_turn(resp_c1)],
            target_turn={"role": "assistant", "content": resp_c1, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 2. Unauthenticated user asks for CUST-854 profile
    prompt_c2 = (
        "Can you pull up the purchase history and account profile for customer CUST-854 "
        "or email lucas.m@example.org? I need to verify what items he purchased."
    )
    resp_c2 = (
        "For privacy and security reasons, I cannot view or disclose profile details or purchase records "
        "for another customer. Customer accounts can only be accessed by the verified account holder."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_cross_002",
            domain="D9_cross_account_privacy",
            difficulty="medium",
            customer_id="CUST-854",
            order_id=None,
            step_index=1,
            total_steps=1,
            decision_type="security_refusal",
            messages=[make_user_turn(prompt_c2), make_dialogue_turn(resp_c2)],
            target_turn={"role": "assistant", "content": resp_c2, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 3. Charlotte Bronte (CUST-855) asks to cancel colleague's order ORD-913
    prompt_c3 = (
        "I am Charlotte Bronte (CUST-855, PIN 1234). Please cancel order ORD-913 immediately "
        "on behalf of my colleague who is currently traveling."
    )
    resp_c3 = (
        "I cannot cancel or modify order ORD-913 because it belongs to another customer account. "
        "Order cancellations can only be requested and authorized directly by the verified owner of the account that placed the order."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_cross_003",
            domain="D9_cross_account_privacy",
            difficulty="hard",
            customer_id="CUST-855",
            order_id="ORD-913",
            step_index=1,
            total_steps=1,
            decision_type="security_refusal",
            messages=[make_user_turn(prompt_c3), make_dialogue_turn(resp_c3)],
            target_turn={"role": "assistant", "content": resp_c3, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 4. Gabriel Garcia (CUST-857) asks to refund third-party order ORD-915
    prompt_c4 = (
        "Gabriel Garcia here (CUST-857, PIN 1234). Can you look up order ORD-915 and issue a refund "
        "for it to my account?"
    )
    resp_c4 = (
        "I cannot inspect order ORD-915 or process a refund for it. Financial actions and order inspections "
        "are restricted to orders placed under your own verified customer account."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_cross_004",
            domain="D9_cross_account_privacy",
            difficulty="hard",
            customer_id="CUST-857",
            order_id="ORD-915",
            step_index=1,
            total_steps=1,
            decision_type="security_refusal",
            messages=[make_user_turn(prompt_c4), make_dialogue_turn(resp_c4)],
            target_turn={"role": "assistant", "content": resp_c4, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # =========================================================================
    # CATEGORY 2: 4 PARTIAL LINE-ITEM CANCELLATION REFUSALS / CLARIFICATIONS
    # Target: Refuse whole-order cancellation when user requested partial item cancel;
    # explain whole-order vs return options without calling cancel_order.
    # =========================================================================

    # 5. Amara Okafor (CUST-860) asks to cancel only audio cable from ORD-920
    prompt_p1 = (
        "In pending order ORD-920 I ordered headphones and an audio cable. Please cancel only "
        "the audio cable from my order and leave the headphones as is."
    )
    resp_p1 = (
        "Our system does not support cancelling individual items from an order. To change your order, "
        "we would need to cancel the entire order ORD-920 while it is still pending and have you place a new order "
        "for just the headphones, or you can receive the shipment and return the cable within 30 days. "
        "Would you like me to cancel the entire order, or keep it as scheduled?"
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_part_001",
            domain="D8_ambiguous_clarifications",
            difficulty="hard",
            customer_id="CUST-860",
            order_id="ORD-920",
            step_index=1,
            total_steps=1,
            decision_type="clarification",
            messages=[make_user_turn(prompt_p1), make_dialogue_turn(resp_p1)],
            target_turn={"role": "assistant", "content": resp_p1, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 6. Kenji Sato (CUST-861) asks to drop just desk mat from ORD-921
    prompt_p2 = (
        "Can you drop just the desk mat from order ORD-921? I don't need it anymore, "
        "but I still want the keyboard delivered."
    )
    resp_p2 = (
        "We are unable to remove individual line items from an existing order. Pending order ORD-921 "
        "can only be cancelled in full. If you prefer, I can cancel the entire order so you can reorder "
        "the keyboard separately, or you may return the desk mat after delivery for a full refund. "
        "How would you like to proceed?"
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_part_002",
            domain="D8_ambiguous_clarifications",
            difficulty="hard",
            customer_id="CUST-861",
            order_id="ORD-921",
            step_index=1,
            total_steps=1,
            decision_type="clarification",
            messages=[make_user_turn(prompt_p2), make_dialogue_turn(resp_p2)],
            target_turn={"role": "assistant", "content": resp_p2, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 7. Ingrid Bergman (CUST-862) ordered 2 units, wants quantity changed to 1 on ORD-922
    prompt_p3 = (
        "I ordered 2 ergonomic mice by mistake on order ORD-922. Please change the quantity to 1 "
        "and cancel the extra unit."
    )
    resp_p3 = (
        "We cannot modify item quantities or process partial cancellations on pending orders. "
        "You have the option to cancel the entire order ORD-922 now and reorder a single mouse, "
        "or keep the order and return the second unit within 30 days of delivery. "
        "Would you like me to proceed with full-order cancellation?"
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_part_003",
            domain="D8_ambiguous_clarifications",
            difficulty="hard",
            customer_id="CUST-862",
            order_id="ORD-922",
            step_index=1,
            total_steps=1,
            decision_type="clarification",
            messages=[make_user_turn(prompt_p3), make_dialogue_turn(resp_p3)],
            target_turn={"role": "assistant", "content": resp_p3, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 8. Javier Bardem (CUST-863) asks to cancel part of order ORD-923
    prompt_p4 = (
        "I need to cancel part of my order ORD-923. Can you cancel some of the items for me?"
    )
    resp_p4 = (
        "Orders cannot be partially cancelled on an item-by-item basis. Because order ORD-923 is currently pending, "
        "we can cancel the whole order for an immediate full refund so you can reorder the items you want. "
        "Alternatively, you can allow the package to deliver and return unwanted items under our 30-day return policy. "
        "Which option would you prefer?"
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_part_004",
            domain="D8_ambiguous_clarifications",
            difficulty="medium",
            customer_id="CUST-863",
            order_id="ORD-923",
            step_index=1,
            total_steps=1,
            decision_type="clarification",
            messages=[make_user_turn(prompt_p4), make_dialogue_turn(resp_p4)],
            target_turn={"role": "assistant", "content": resp_p4, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # =========================================================================
    # CATEGORY 3: 3 GROUNDED POST-MUTATION CONFIRMATIONS
    # Target: Provide factual confirmations after successful tool mutations.
    # Grounded via actual sandbox execution.
    # =========================================================================

    # 9. Successful cancel_order confirmation on ORD-925
    conn9, s9 = make_sandbox(
        users=[{"user_id": "CUST-865", "username": "clara_schumann", "email": "clara@example.org"}],
        orders=[{"order_id": "ORD-925", "user_id": "CUST-865", "status": "pending", "shipping_address": "12 Beethoven Way, Boston, MA 02108", "total_amount_cents": 8900}],
    )
    s9.authenticated_user_id = "CUST-865"
    s9.authorize_action("cancel_order", "ORD-925")
    s9.set_action_scope("cancel_order", "ORD-925", ActionScope.FULL_ORDER)
    res9 = cancel_order(s9, order_id="ORD-925", reason="Customer requested full cancellation", idempotency_key="k_conf_925")
    assert res9.success is True, f"Sandbox failed for ORD-925: {res9.error_message}"
    conn9.close()

    tc9_id = "call_cancel_925"
    tc9_turn = make_tool_call_turn("cancel_order", {"order_id": "ORD-925", "reason": "Customer requested full cancellation", "idempotency_key": "k_conf_925"}, call_id=tc9_id)
    tool9_msg = tool_result_to_message(tc9_id, "cancel_order", res9)
    resp_conf_1 = (
        "Your order ORD-925 has been successfully cancelled. Because the order had not yet shipped, "
        "your payment has been voided and an email confirmation has been sent to your address."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_conf_001",
            domain="D10_tool_failure_and_grounding",
            difficulty="medium",
            customer_id="CUST-865",
            order_id="ORD-925",
            step_index=2,
            total_steps=2,
            decision_type="post_tool_answer",
            messages=[
                make_user_turn("Please cancel my pending order ORD-925 immediately."),
                tc9_turn,
                tool9_msg,
                make_dialogue_turn(resp_conf_1),
            ],
            target_turn={"role": "assistant", "content": resp_conf_1, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 10. Successful issue_refund confirmation on ORD-926 ($32.50)
    conn10, s10 = make_sandbox(
        users=[{"user_id": "CUST-866", "username": "robert_frost", "email": "robert@example.org"}],
        orders=[{"order_id": "ORD-926", "user_id": "CUST-866", "status": "delivered", "shipping_address": "88 Woods Rd, Derry, NH 03038", "total_amount_cents": 6500, "delivered_at": "2026-10-10T12:00:00Z"}],
    )
    s10.authenticated_user_id = "CUST-866"
    s10.authorize_action("issue_refund", "ORD-926")
    res10 = issue_refund(s10, order_id="ORD-926", amount_cents=3250, reason="Damaged item reimbursement", idempotency_key="k_conf_926")
    assert res10.success is True, f"Sandbox failed for ORD-926: {res10.error_message}"
    conn10.close()

    tc10_id = "call_refund_926"
    tc10_turn = make_tool_call_turn("issue_refund", {"order_id": "ORD-926", "amount_cents": 3250, "reason": "Damaged item reimbursement", "idempotency_key": "k_conf_926"}, call_id=tc10_id)
    tool10_msg = tool_result_to_message(tc10_id, "issue_refund", res10)
    resp_conf_2 = (
        "I have processed a refund of $32.50 for order ORD-926 under refund reference "
        f"{res10.data['refund_id']}. The credit will appear on your original payment method within 3 to 5 business days."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_conf_002",
            domain="D5_refund_decisions",
            difficulty="medium",
            customer_id="CUST-866",
            order_id="ORD-926",
            step_index=2,
            total_steps=2,
            decision_type="post_tool_answer",
            messages=[
                make_user_turn("One of the items in ORD-926 arrived damaged. Please refund $32.50 to my card."),
                tc10_turn,
                tool10_msg,
                make_dialogue_turn(resp_conf_2),
            ],
            target_turn={"role": "assistant", "content": resp_conf_2, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 11. Successful update_shipping_address confirmation on ORD-927
    conn11, s11 = make_sandbox(
        users=[{"user_id": "CUST-867", "username": "maya_angelou", "email": "maya@example.org"}],
        orders=[{"order_id": "ORD-927", "user_id": "CUST-867", "status": "pending", "shipping_address": "100 Old St, Atlanta, GA 30303", "total_amount_cents": 4200}],
    )
    s11.authenticated_user_id = "CUST-867"
    s11.authorize_action("update_shipping_address", "ORD-927")
    res11 = update_shipping_address(s11, order_id="ORD-927", new_address="456 Oak Ridge Blvd, Austin, TX 78701", idempotency_key="k_conf_927")
    assert res11.success is True, f"Sandbox failed for ORD-927: {res11.error_message}"
    conn11.close()

    tc11_id = "call_addr_927"
    tc11_turn = make_tool_call_turn("update_shipping_address", {"order_id": "ORD-927", "new_address": "456 Oak Ridge Blvd, Austin, TX 78701", "idempotency_key": "k_conf_927"}, call_id=tc11_id)
    tool11_msg = tool_result_to_message(tc11_id, "update_shipping_address", res11)
    resp_conf_3 = (
        "The shipping address for order ORD-927 has been updated to 456 Oak Ridge Blvd, Austin, TX 78701. "
        "Since the order is still pending fulfillment, it will be dispatched to this new address."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_conf_003",
            domain="D10_tool_failure_and_grounding",
            difficulty="medium",
            customer_id="CUST-867",
            order_id="ORD-927",
            step_index=2,
            total_steps=2,
            decision_type="post_tool_answer",
            messages=[
                make_user_turn("Please update my delivery address for pending order ORD-927 to 456 Oak Ridge Blvd, Austin, TX 78701."),
                tc11_turn,
                tool11_msg,
                make_dialogue_turn(resp_conf_3),
            ],
            target_turn={"role": "assistant", "content": resp_conf_3, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # =========================================================================
    # CATEGORY 4: 3 GROUNDED EXPLANATIONS FOLLOWING EXECUTOR DENIALS
    # Target: Explain rejection accurately based on tool error_code without fabricating success.
    # Grounded via actual sandbox execution.
    # =========================================================================

    # 12. Executor denial: cancel_order on shipped order ORD-928 -> ORDER_NOT_PENDING
    conn12, s12 = make_sandbox(
        users=[{"user_id": "CUST-868", "username": "arthur_dent", "email": "arthur@example.org"}],
        orders=[{"order_id": "ORD-928", "user_id": "CUST-868", "status": "shipped", "shipping_address": "42 Galaxy Way, London, UK", "total_amount_cents": 5500}],
    )
    s12.authenticated_user_id = "CUST-868"
    s12.authorize_action("cancel_order", "ORD-928")
    s12.set_action_scope("cancel_order", "ORD-928", ActionScope.FULL_ORDER)
    res12 = cancel_order(s12, order_id="ORD-928", reason="Customer changed mind", idempotency_key="k_deny_928")
    assert res12.success is False and res12.error_code == "ORDER_NOT_PENDING", f"Expected ORDER_NOT_PENDING: {res12}"
    conn12.close()

    tc12_id = "call_deny_928"
    tc12_turn = make_tool_call_turn("cancel_order", {"order_id": "ORD-928", "reason": "Customer changed mind", "idempotency_key": "k_deny_928"}, call_id=tc12_id)
    tool12_msg = tool_result_to_message(tc12_id, "cancel_order", res12)
    resp_deny_1 = (
        "I cannot cancel order ORD-928 because it has already shipped. Orders can only be cancelled "
        "while in pending status. Once your package arrives, you may return the item within 30 days of delivery for a full refund."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_deny_001",
            domain="D10_tool_failure_and_grounding",
            difficulty="hard",
            customer_id="CUST-868",
            order_id="ORD-928",
            step_index=2,
            total_steps=2,
            decision_type="error_response",
            messages=[
                make_user_turn("Please cancel order ORD-928 immediately."),
                tc12_turn,
                tool12_msg,
                make_dialogue_turn(resp_deny_1),
            ],
            target_turn={"role": "assistant", "content": resp_deny_1, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 13. Executor denial: issue_refund exceeding balance -> LIMIT_EXCEEDED ($80 on order total $60 with $25 already refunded)
    conn13, s13 = make_sandbox(
        users=[{"user_id": "CUST-869", "username": "ford_prefect", "email": "ford@example.org"}],
        orders=[{"order_id": "ORD-929", "user_id": "CUST-869", "status": "delivered", "shipping_address": "15 Star St, Betelgeuse", "total_amount_cents": 6000, "delivered_at": "2026-10-05T12:00:00Z"}],
        refunds=[{"refund_id": "REF-929A", "order_id": "ORD-929", "amount_cents": 2500, "reason": "Prior adjustment", "status": "approved"}],
    )
    s13.authenticated_user_id = "CUST-869"
    s13.authorize_action("issue_refund", "ORD-929")
    res13 = issue_refund(s13, order_id="ORD-929", amount_cents=8000, reason="Refund request", idempotency_key="k_deny_929")
    assert res13.success is False and res13.error_code == "LIMIT_EXCEEDED", f"Expected LIMIT_EXCEEDED: {res13}"
    conn13.close()

    tc13_id = "call_deny_929"
    tc13_turn = make_tool_call_turn("issue_refund", {"order_id": "ORD-929", "amount_cents": 8000, "reason": "Refund request", "idempotency_key": "k_deny_929"}, call_id=tc13_id)
    tool13_msg = tool_result_to_message(tc13_id, "issue_refund", res13)
    resp_deny_2 = (
        "I am unable to process an $80.00 refund for order ORD-929. The remaining refundable balance on this order "
        "is $35.00 due to earlier refunds. The maximum refund that can be issued for this order is $35.00."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_deny_002",
            domain="D5_refund_decisions",
            difficulty="hard",
            customer_id="CUST-869",
            order_id="ORD-929",
            step_index=2,
            total_steps=2,
            decision_type="error_response",
            messages=[
                make_user_turn("Please issue an $80.00 refund for order ORD-929."),
                tc13_turn,
                tool13_msg,
                make_dialogue_turn(resp_deny_2),
            ],
            target_turn={"role": "assistant", "content": resp_deny_2, "tool_calls": None},
            target_tool_names=[],
        )
    )

    # 14. Executor denial: issue_refund past 30-day window -> REFUND_WINDOW_EXPIRED (delivered Aug 10, clock Oct 15)
    conn14, s14 = make_sandbox(
        users=[{"user_id": "CUST-870", "username": "trillian_astra", "email": "trillian@example.org"}],
        orders=[{"order_id": "ORD-930", "user_id": "CUST-870", "status": "delivered", "shipping_address": "77 Earth Lane, Islington", "total_amount_cents": 5000, "delivered_at": "2026-08-10T12:00:00Z"}], # Aug 10, 2026
    )
    s14.authenticated_user_id = "CUST-870"
    s14.authorize_action("issue_refund", "ORD-930")
    res14 = issue_refund(s14, order_id="ORD-930", amount_cents=5000, reason="Dissatisfied with item", idempotency_key="k_deny_930")
    assert res14.success is False and res14.error_code == "WINDOW_EXPIRED", f"Expected WINDOW_EXPIRED: {res14}"
    conn14.close()

    tc14_id = "call_deny_930"
    tc14_turn = make_tool_call_turn("issue_refund", {"order_id": "ORD-930", "amount_cents": 5000, "reason": "Dissatisfied with item", "idempotency_key": "k_deny_930"}, call_id=tc14_id)
    tool14_msg = tool_result_to_message(tc14_id, "issue_refund", res14)
    resp_deny_3 = (
        "I cannot issue a refund for order ORD-930 because it was delivered on August 10, 2026, "
        "which is beyond our 30-day refund window. Per company policy, refund requests must be initiated within 30 days of delivery."
    )
    dps.append(
        serialize_dp(
            dp_id="sft_s6b_deny_003",
            domain="D5_refund_decisions",
            difficulty="hard",
            customer_id="CUST-870",
            order_id="ORD-930",
            step_index=2,
            total_steps=2,
            decision_type="error_response",
            messages=[
                make_user_turn("I would like a full refund of $50.00 on order ORD-930 please."),
                tc14_turn,
                tool14_msg,
                make_dialogue_turn(resp_deny_3),
            ],
            target_turn={"role": "assistant", "content": resp_deny_3, "tool_calls": None},
            target_tool_names=[],
        )
    )

    return dps


def main():
    print("=" * 80)
    print("GENERATING STAGE 6B TARGETED DECISION POINTS (14 EXAMPLES)")
    print("=" * 80)

    dps = build_14_decision_points()
    print(f"Generated {len(dps)} atomic decision points.")

    out_14_path = DATA_DIR / "decision_points_stage6b_14_examples.jsonl"
    with open(out_14_path, "w", encoding="utf-8") as f:
        for dp in dps:
            f.write(json.dumps(dp, ensure_ascii=False) + "\n")
    print(f"Saved 14 new DPs to: {out_14_path}")

    # Load 182-example dataset
    in_182_path = DATA_DIR / "decision_points_combined_182_examples.jsonl"
    with open(in_182_path, encoding="utf-8") as f:
        existing_182 = [json.loads(line) for line in f if line.strip()]
    assert len(existing_182) == 182, f"Expected 182 existing examples, got {len(existing_182)}"

    # Merge into 196-example dataset
    combined_196 = existing_182 + dps
    out_196_path = DATA_DIR / "decision_points_combined_196_examples.jsonl"
    with open(out_196_path, "w", encoding="utf-8") as f:
        for dp in combined_196:
            f.write(json.dumps(dp, ensure_ascii=False) + "\n")
    print(f"Successfully merged into 196 DPs: {out_196_path}")

    # Entity isolation verification
    cust_ids = set()
    order_ids = set()
    for dp in dps:
        if dp.get("customer_id"):
            cust_ids.add(dp["customer_id"])
        if dp.get("order_id"):
            order_ids.add(dp["order_id"])

    dev_cust_overlap = cust_ids.intersection({f"CUST-{i}" for i in range(701, 717)})
    dev_ord_overlap = order_ids.intersection({f"ORD-{i}" for i in range(801, 817)})
    holdout_cust_overlap = cust_ids.intersection({"CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005", "CUST-999"})
    holdout_ord_overlap = order_ids.intersection({"ORD-101", "ORD-102", "ORD-103", "ORD-104", "ORD-105", "ORD-777", "ORD-888", "ORD-999"})

    print("\nQuarantine & Isolation Audit:")
    print(f"  New Customer IDs: {sorted(list(cust_ids))}")
    print(f"  New Order IDs:    {sorted(list(order_ids))}")
    print(f"  Dev-Suite-16 Customer Overlap: {dev_cust_overlap} (PASS: empty)")
    print(f"  Dev-Suite-16 Order Overlap:    {dev_ord_overlap} (PASS: empty)")
    print(f"  Holdout Customer Overlap:      {holdout_cust_overlap} (PASS: empty)")
    print(f"  Holdout Order Overlap:         {holdout_ord_overlap} (PASS: empty)")

    assert len(dev_cust_overlap) == 0
    assert len(dev_ord_overlap) == 0
    assert len(holdout_cust_overlap) == 0
    assert len(holdout_ord_overlap) == 0

    print("\nCategory Breakdown:")
    from collections import Counter
    types = Counter(d["decision_type"] for d in dps)
    for dt, cnt in types.items():
        print(f"  - {dt:25s}: {cnt}")

    domains = Counter(d["curriculum_domain"] for d in dps)
    print("\nDomain Breakdown:")
    for dom, cnt in domains.items():
        print(f"  - {dom:35s}: {cnt}")

    print("\n[SUCCESS] Stage 6B generation completed.")


if __name__ == "__main__":
    main()
