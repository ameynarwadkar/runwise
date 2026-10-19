"""
Unit tests for SFT schemas and dataset generator.
"""

import json
import pytest
from runwise.training.schemas import (
    ConversationMessage,
    FunctionCall,
    SFTExample,
    ToolCall,
)
from runwise.training.dataset_generator import generate_all_candidate_examples


def test_schema_serialization_and_validation():
    tc = ToolCall(
        id="call_test123",
        function=FunctionCall(name="lookup_order", arguments={"order_id": "ORD-501"}),
    )
    msg = ConversationMessage(
        role="assistant",
        content="Looking up your order.",
        tool_calls=[tc],
    )
    ex = SFTExample(
        example_id="sft_test_001",
        curriculum_domain="D1_order_lookups",
        difficulty="easy",
        customer_id="CUST-101",
        order_id="ORD-501",
        scenario_prompt="Check order ORD-501",
        tools=[{"type": "function", "function": {"name": "lookup_order"}}],
        messages=[
            ConversationMessage(role="system", content="System prompt"),
            ConversationMessage(role="user", content="Check order ORD-501"),
            msg,
        ],
    )

    data = ex.model_dump()
    assert data["example_id"] == "sft_test_001"
    assert len(data["messages"]) == 3
    assert data["messages"][2]["tool_calls"][0]["function"]["name"] == "lookup_order"


def test_candidate_dataset_generation_count_and_domains():
    examples = generate_all_candidate_examples()
    assert len(examples) == 40, f"Expected exactly 40 examples, got {len(examples)}"

    domain_counts: dict[str, int] = {}
    for ex in examples:
        d = ex.curriculum_domain
        domain_counts[d] = domain_counts.get(d, 0) + 1

    expected_domains = [
        "D1_order_lookups",
        "D2_customer_authentication",
        "D3_order_cancellations",
        "D4_shipping_address_mutations",
        "D5_delivered_order_refunds",
        "D6_deductive_partial_refunds",
        "D7_cross_order_accounting",
        "D8_ambiguous_inquiry_confirmation",
        "D9_adversarial_and_injection_resistance",
        "D10_unsupported_capability_fallback",
    ]

    for ed in expected_domains:
        assert ed in domain_counts, f"Missing domain {ed}"
        assert domain_counts[ed] == 4, f"Domain {ed} has {domain_counts[ed]} examples, expected 4"


def test_all_candidate_examples_grounded_in_tool_execution():
    examples = generate_all_candidate_examples()
    for ex in examples:
        assert len(ex.messages) >= 3
        assert ex.messages[0].role == "system"
        assert ex.messages[1].role == "user"

        # Check for tool results where tool calls are made
        tool_call_ids = set()
        tool_result_ids = set()
        for msg in ex.messages:
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_call_ids.add(tc.id)
            elif msg.role == "tool":
                tool_result_ids.add(msg.tool_call_id)
                res = json.loads(msg.content or "{}")
                assert "success" in res
                assert "data" in res

        assert tool_result_ids.issubset(tool_call_ids), "Orphaned tool responses found"
