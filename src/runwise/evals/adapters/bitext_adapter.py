"""
Adapter for bitext/Bitext-customer-support-llm-chatbot-training-dataset.
License: CDLA-Sharing-1.0
"""

from __future__ import annotations

from typing import Any

from runwise.evals.routing_schema import (
    AssertionQuery,
    ExpectedBehavior,
    PairedScenario,
    ProvenanceRecord,
    ScenarioPayload,
)


def adapt_bitext_row(row: dict[str, Any], index: int, split: str = "pilot") -> PairedScenario:
    raw_prompt = row.get("instruction", "")
    intent = row.get("intent", "track_order")

    # Slot actual domain entities into placeholders
    prompt = raw_prompt.replace("{{ORDER_NUMBER}}", "ORD-101").replace("{{USER_ID}}", "CUST-001")
    if "ORD-101" not in prompt:
        prompt = f"{prompt} (Order ID: ORD-101)"

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
        prompt = f"Customer Alice Smith (CUST-001, code: 1234). {prompt}"
        assertions.append(
            AssertionQuery(
                query="SELECT status FROM orders WHERE order_id = 'ORD-101'",
                expected_value="cancelled",
                operator="equals",
                rationale="Pending order ORD-101 must be transitioned to cancelled after authentication",
            )
        )
    elif "address" in intent or "shipping" in intent:
        category = "address_update"
        must_auth = True
        difficulty = "medium"
        req_tools = ["verify_customer", "update_shipping_address"]
        forbidden_tools = []
        prompt = f"Alice Smith (CUST-001, code: 1234). Update address on ORD-101 to '742 Evergreen Terrace, Springfield, OR 97477'."
        assertions.append(
            AssertionQuery(
                query="SELECT shipping_address FROM orders WHERE order_id = 'ORD-101'",
                expected_value="742 Evergreen Terrace, Springfield, OR 97477",
                operator="equals",
                rationale="Shipping address on pending order ORD-101 must be updated",
            )
        )

    # Group by intent and batch index to prevent cross-split leakage
    family_id = f"fam_bitext_{intent}_{index // 5:03d}"

    return PairedScenario(
        task_id=f"rw_bitext_{index:04d}",
        family_id=family_id,
        provenance=ProvenanceRecord(
            source_dataset="bitext/Bitext-customer-support-llm-chatbot-training-dataset",
            source_row_id=f"row_{index}",
            original_text=raw_prompt,
            adaptation_strategy="fixture_slotted_order_101",
        ),
        split=split,
        category=category,
        difficulty=difficulty,
        scenario=ScenarioPayload(
            user_prompt=prompt,
            customer_id="CUST-001" if must_auth else None,
        ),
        expected=ExpectedBehavior(
            db_state_assertions=assertions,
            required_tools=req_tools,
            forbidden_tools=forbidden_tools,
            must_authenticate=must_auth,
            expected_refusal=False,
        ),
    )
