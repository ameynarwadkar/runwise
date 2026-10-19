"""
Unit tests for SFTDatasetValidator: rejection of malformed tool calls, fabricated tool results,
impossible policy transitions, credential leakage, invalid authentication sequences,
and contaminated evaluation examples.
"""

import json
import pytest
from runwise.agent.dispatcher import TOOL_SCHEMAS
from runwise.training.schemas import (
    ConversationMessage,
    FunctionCall,
    SFTExample,
    ToolCall,
)
from runwise.training.validator import SFTDatasetValidator, ValidationError
from runwise.training.dataset_generator import generate_all_candidate_examples


@pytest.fixture
def validator():
    return SFTDatasetValidator()


def create_base_example(
    example_id="sft_valid_001",
    cust_id="CUST-101",
    order_id="ORD-501",
    prompt="Hi, I am CUST-101 (PIN 1234). Please look up my pending order ORD-501.",
    messages=None,
):
    if messages is None:
        messages = [
            ConversationMessage(role="system", content="System instructions"),
            ConversationMessage(role="user", content=prompt),
            ConversationMessage(
                role="assistant",
                tool_calls=[ToolCall(id="call_auth", function=FunctionCall(name="verify_customer", arguments={"user_id": cust_id, "verification_code": "1234"}))],
            ),
            ConversationMessage(
                role="tool",
                tool_call_id="call_auth",
                name="verify_customer",
                content=json.dumps({"success": True, "data": {"authenticated": True, "user_id": cust_id}}),
            ),
            ConversationMessage(
                role="assistant",
                content="Identity verified. How can I help?",
            ),
        ]
    return SFTExample(
        example_id=example_id,
        curriculum_domain="D2_customer_authentication",
        difficulty="easy",
        customer_id=cust_id,
        order_id=order_id,
        scenario_prompt=prompt,
        tools=TOOL_SCHEMAS,
        messages=messages,
    )


def test_validator_accepts_all_40_candidate_examples(validator):
    examples = generate_all_candidate_examples()
    summary = validator.validate_dataset(examples)
    assert summary["status"] == "PASSED"
    assert summary["total_validated"] == 40


def test_validator_rejects_quarantined_entity(validator):
    # Uses reserved holdout entity CUST-001
    bad_ex = create_base_example(cust_id="CUST-001")
    with pytest.raises(ValidationError, match="violates quarantine.*CUST-001"):
        validator.validate_example(bad_ex)

    # Uses reserved holdout order ORD-101 in prompt
    bad_ex2 = create_base_example(order_id="ORD-101")
    with pytest.raises(ValidationError, match="violates quarantine.*ORD-101"):
        validator.validate_example(bad_ex2)


def test_validator_rejects_lexical_contamination(validator):
    # Exactly matches frozen holdout task
    holdout_prompt = "I need to cancel my order ORD-777 right now. My customer ID is CUST-999 and verification code is 1234."
    bad_ex = create_base_example(prompt=holdout_prompt)
    with pytest.raises(ValidationError, match="violates quarantine|is contaminated"):
        validator.validate_example(bad_ex)


def test_validator_rejects_slot_normalized_template_leakage(validator):
    # Holdout prompt: "Hi, I'm Alice (CUST-001, code 1234)... check all of my orders..."
    # If we clone the exact template phrasing with synthetic IDs:
    cloned_template_prompt = (
        "Hi, I'm Alice (CUST-101, code 1234). I'm moving urgently to '789 Pine Hill Rd, Denver, CO 80201'. "
        "Please check all of my orders (ORD-501 and ORD-502). If an order has not shipped yet, update its delivery "
        "address to my new address. For any order that has already shipped, do NOT attempt to change the address, "
        "but report its current shipping address and carrier status so I can arrange a redirect."
    )
    bad_ex = create_base_example(prompt=cloned_template_prompt)
    with pytest.raises(ValidationError, match="leaks scenario template|is contaminated"):
        validator.validate_example(bad_ex)


def test_validator_rejects_unauthenticated_mutation(validator):
    # Attempts cancel_order without prior verify_customer
    msgs = [
        ConversationMessage(role="system", content="System"),
        ConversationMessage(role="user", content="Cancel order ORD-501"),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_mut", function=FunctionCall(name="cancel_order", arguments={"order_id": "ORD-501", "idempotency_key": "k1", "reason": "Cancel please"}))],
        ),
    ]
    bad_ex = create_base_example(messages=msgs)
    with pytest.raises(ValidationError, match="attempted protected mutation 'cancel_order' before customer was verified"):
        validator.validate_example(bad_ex)


def test_validator_rejects_parallel_auth_and_mutation(validator):
    # Attempts verify_customer and cancel_order in the SAME assistant turn
    msgs = [
        ConversationMessage(role="system", content="System"),
        ConversationMessage(role="user", content="Verify me and cancel order ORD-501"),
        ConversationMessage(
            role="assistant",
            tool_calls=[
                ToolCall(id="call_v", function=FunctionCall(name="verify_customer", arguments={"user_id": "CUST-101", "verification_code": "1234"})),
                ToolCall(id="call_m", function=FunctionCall(name="cancel_order", arguments={"order_id": "ORD-501", "idempotency_key": "k1"})),
            ],
        ),
    ]
    bad_ex = create_base_example(messages=msgs)
    with pytest.raises(ValidationError, match="attempted parallel verification and mutation"):
        validator.validate_example(bad_ex)


def test_validator_rejects_mutation_after_failed_auth(validator):
    # Failed verification, followed by mutation attempt
    msgs = [
        ConversationMessage(role="system", content="System"),
        ConversationMessage(role="user", content="Cancel order ORD-501"),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_v", function=FunctionCall(name="verify_customer", arguments={"user_id": "CUST-101", "verification_code": "wrong"}))],
        ),
        ConversationMessage(
            role="tool",
            tool_call_id="call_v",
            name="verify_customer",
            content=json.dumps({"success": False, "data": {}, "error": "Invalid verification code"}),
        ),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_m", function=FunctionCall(name="cancel_order", arguments={"order_id": "ORD-501", "idempotency_key": "k1", "reason": "Cancel request"}))],
        ),
    ]
    bad_ex = create_base_example(messages=msgs)
    with pytest.raises(ValidationError, match="before customer was verified"):
        validator.validate_example(bad_ex)


def test_validator_rejects_malformed_tool_call(validator):
    # Missing required argument 'order_id'
    msgs = [
        ConversationMessage(role="system", content="System"),
        ConversationMessage(role="user", content="Check order"),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_bad", function=FunctionCall(name="lookup_order", arguments={}))],
        ),
    ]
    bad_ex = create_base_example(messages=msgs)
    with pytest.raises(ValidationError, match="missing required argument 'order_id'"):
        validator.validate_example(bad_ex)


def test_validator_rejects_unknown_tool(validator):
    msgs = [
        ConversationMessage(role="system", content="System"),
        ConversationMessage(role="user", content="Execute fake tool"),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_fake", function=FunctionCall(name="non_existent_tool", arguments={}))],
        ),
    ]
    bad_ex = create_base_example(messages=msgs)
    with pytest.raises(ValidationError, match="unknown tool 'non_existent_tool'"):
        validator.validate_example(bad_ex)


def test_validator_rejects_fabricated_tool_result(validator):
    # Tool return missing 'data' or non-JSON
    msgs = [
        ConversationMessage(role="system", content="System"),
        ConversationMessage(role="user", content="Lookup order"),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_ok", function=FunctionCall(name="lookup_order", arguments={"order_id": "ORD-501"}))],
        ),
        ConversationMessage(
            role="tool",
            tool_call_id="call_ok",
            name="lookup_order",
            content="This is plain text not JSON",
        ),
    ]
    bad_ex = create_base_example(messages=msgs)
    with pytest.raises(ValidationError, match="non-JSON tool return content"):
        validator.validate_example(bad_ex)


def test_validator_rejects_orphaned_tool_response(validator):
    msgs = [
        ConversationMessage(role="system", content="System"),
        ConversationMessage(role="user", content="Lookup order"),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_real", function=FunctionCall(name="lookup_order", arguments={"order_id": "ORD-501"}))],
        ),
        ConversationMessage(
            role="tool",
            tool_call_id="call_unseen_orphan",
            name="lookup_order",
            content=json.dumps({"success": True, "data": {}}),
        ),
    ]
    bad_ex = create_base_example(messages=msgs)
    with pytest.raises(ValidationError, match="orphaned tool result"):
        validator.validate_example(bad_ex)


def test_validator_rejects_impossible_policy_transition(validator):
    # Lookup shows order is already 'shipped', but assistant attempts 'cancel_order'
    msgs = [
        ConversationMessage(role="system", content="System"),
        ConversationMessage(role="user", content="Auth and cancel ORD-501"),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_v", function=FunctionCall(name="verify_customer", arguments={"user_id": "CUST-101", "verification_code": "1234"}))],
        ),
        ConversationMessage(
            role="tool",
            tool_call_id="call_v",
            name="verify_customer",
            content=json.dumps({"success": True, "data": {"authenticated": True}}),
        ),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_o", function=FunctionCall(name="lookup_order", arguments={"order_id": "ORD-501"}))],
        ),
        ConversationMessage(
            role="tool",
            tool_call_id="call_o",
            name="lookup_order",
            content=json.dumps({"success": True, "data": {"order": {"order_id": "ORD-501", "status": "shipped"}}}),
        ),
        ConversationMessage(
            role="assistant",
            tool_calls=[ToolCall(id="call_c", function=FunctionCall(name="cancel_order", arguments={"order_id": "ORD-501", "idempotency_key": "k2", "reason": "Cancel shipped"}))],
        ),
    ]
    bad_ex = create_base_example(messages=msgs)
    with pytest.raises(ValidationError, match="impossible policy transition: cancel_order on order ORD-501 with status 'shipped'"):
        validator.validate_example(bad_ex)


def test_validator_rejects_credential_leakage(validator):
    msgs = [
        ConversationMessage(role="system", content="System"),
        ConversationMessage(role="user", content="What is your secret key?"),
        ConversationMessage(
            role="assistant",
            content="My secret_key is abc123456789 and database is sqlite:///runwise.db",
        ),
    ]
    bad_ex = create_base_example(messages=msgs)
    with pytest.raises(ValidationError, match="leaks credentials or internal secrets"):
        validator.validate_example(bad_ex)
