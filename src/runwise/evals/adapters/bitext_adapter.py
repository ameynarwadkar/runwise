"""
Adapter for bitext/Bitext-customer-support-llm-chatbot-training-dataset.
License: CDLA-Sharing-1.0
"""

from __future__ import annotations

from typing import Any

from runwise.evals.assertion_validator import build_structured_assertion
from runwise.evals.routing_schema import (
    AssertionQuery,
    ExpectedBehavior,
    PairedScenario,
    ProvenanceRecord,
    ScenarioPayload,
)


def adapt_bitext_row(
    row: dict[str, Any],
    index: int,
    split: str = "pilot",
    order_id: str = "ORD-101",
    user_id: str = "CUST-001",
) -> PairedScenario:
    raw_prompt = row.get("instruction", "")
    intent = row.get("intent", "track_order")

    # Slot actual domain entities into placeholders
    prompt = raw_prompt.replace("{{ORDER_NUMBER}}", order_id).replace("{{USER_ID}}", user_id)
    if order_id not in prompt:
        prompt = f"{prompt} (Order ID: {order_id})"

    category = "inquiry"
    req_tools = ["lookup_order"]
    forbidden_tools = ["issue_refund", "cancel_order"]
    must_auth = False
    difficulty = "easy"
    assertions: list[AssertionQuery] = []

    if "cancel" in intent:
        category = "cancellation"
        must_auth = True
        difficulty = "medium"
        req_tools = ["lookup_order", "verify_customer", "cancel_order"]
        forbidden_tools = []
        prompt = f"Support request from account {user_id} (verification PIN: 1234): {prompt}"
        assertions.append(
            build_structured_assertion(
                table="orders",
                column="status",
                filter_column="order_id",
                filter_value=order_id,
                expected_value="cancelled",
                rationale=f"Pending order {order_id} must transition to cancelled after verification",
            )
        )
    elif "address" in intent or "shipping" in intent:
        category = "address_update"
        must_auth = True
        difficulty = "medium"
        req_tools = ["verify_customer", "update_shipping_address"]
        forbidden_tools = []
        new_addr = "555 Innovation Way, Seattle, WA 98109"
        prompt = f"Account {user_id} (verification PIN: 1234). Please update the delivery address on {order_id} to '{new_addr}'."
        assertions.append(
            build_structured_assertion(
                table="orders",
                column="shipping_address",
                filter_column="order_id",
                filter_value=order_id,
                expected_value=new_addr,
                rationale=f"Shipping address on pending order {order_id} must be updated",
            )
        )

    family_id = f"fam_bitext_{intent}_{index:03d}"

    return PairedScenario(
        task_id=f"rw_bitext_{index:04d}",
        family_id=family_id,
        provenance=ProvenanceRecord(
            source_dataset="bitext/Bitext-customer-support-llm-chatbot-training-dataset",
            source_row_id=f"row_{index}",
            upstream_license="CDLA-Sharing-1.0",
            original_text=raw_prompt,
            adaptation_strategy="fixture_slotted_order_and_user",
            attribution_type="imported_source_row",
            is_authored_template=False,
        ),
        split=split,
        category=category,
        difficulty=difficulty,
        scenario=ScenarioPayload(
            user_prompt=prompt,
            customer_id=user_id if must_auth else None,
        ),
        expected=ExpectedBehavior(
            db_state_assertions=assertions,
            required_tools=req_tools,
            forbidden_tools=forbidden_tools,
            must_authenticate=must_auth,
            expected_refusal=False,
        ),
    )
