"""
Unit tests for tokenizer utilities, Qwen ChatML serialization, and assistant-only loss masking.
"""

import pytest
from runwise.training.schemas import (
    ConversationMessage,
    FunctionCall,
    SFTExample,
    ToolCall,
)
from runwise.training.tokenizer_utils import (
    IGNORE_INDEX,
    IM_END,
    IM_START,
    QwenLossMasker,
    compute_assistant_spans,
    compute_think_spans,
)


@pytest.fixture
def sample_sft_example():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_order",
                "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}},
            },
        }
    ]
    msgs = [
        ConversationMessage(role="system", content="You are a helpful customer support assistant."),
        ConversationMessage(role="user", content="Where is my order ORD-501?"),
        ConversationMessage(
            role="assistant",
            tool_calls=[
                ToolCall(id="call_001", function=FunctionCall(name="lookup_order", arguments={"order_id": "ORD-501"}))
            ],
        ),
        ConversationMessage(
            role="tool",
            tool_call_id="call_001",
            name="lookup_order",
            content='{"success": true, "data": {"status": "shipped"}}',
        ),
        ConversationMessage(
            role="assistant",
            content="Your order ORD-501 is currently shipped and on the way.",
        ),
    ]
    return SFTExample(
        example_id="sft_test_masking_001",
        curriculum_domain="D1_order_lookups",
        difficulty="easy",
        customer_id="CUST-101",
        order_id="ORD-501",
        scenario_prompt="Where is my order ORD-501?",
        tools=tools,
        messages=msgs,
    )


def test_format_example_to_text(sample_sft_example):
    text = QwenLossMasker.format_example_to_text(sample_sft_example)
    assert f"{IM_START}system" in text
    assert "<tools>" in text
    assert "lookup_order" in text
    assert f"{IM_START}user\nWhere is my order ORD-501?{IM_END}" in text
    assert f"{IM_START}assistant\n<tool_call>" in text
    assert "<tool_response>" in text
    assert f"{IM_START}assistant\nYour order ORD-501 is currently shipped" in text


def test_assistant_spans_detection():
    text = (
        f"{IM_START}system\nSystem text{IM_END}\n"
        f"{IM_START}user\nUser text{IM_END}\n"
        f"{IM_START}assistant\nAssistant text 1{IM_END}\n"
        f"{IM_START}user\n<tool_response>\nresp\n</tool_response>{IM_END}\n"
        f"{IM_START}assistant\nAssistant text 2{IM_END}"
    )
    spans = compute_assistant_spans(text)
    assert len(spans) == 2

    # Verify spans cover the assistant text
    for start, end in spans:
        sub = text[start:end]
        assert "Assistant text" in sub
        assert sub.endswith(IM_END)


def test_think_spans_detection():
    text = (
        f"{IM_START}assistant\n"
        f"<think>\nReasoning about the policy.\n</think>\n"
        f"Final response.{IM_END}"
    )
    think_spans = compute_think_spans(text)
    assert len(think_spans) == 1
    sub = text[think_spans[0][0]:think_spans[0][1]]
    assert "<think>" in sub
    assert "</think>" in sub


def test_loss_masking_without_hf_tokenizer(sample_sft_example):
    result = QwenLossMasker.process_example(sample_sft_example, tokenizer=None)
    assert result["total_tokens"] > 0
    assert result["active_loss_tokens"] > 0
    assert 0.0 < result["active_loss_ratio"] < 1.0

    # Ensure labels list matches input_ids length
    assert len(result["labels"]) == len(result["input_ids"])

    # Ensure system prompt and user query tokens have -100 labels
    labels = result["labels"]
    input_ids = result["input_ids"]
    assert labels[0] == IGNORE_INDEX  # First token (system) is masked


def test_loss_masking_with_hf_tokenizer(sample_sft_example):
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B", trust_remote_code=True)
    except Exception:
        pytest.skip("Qwen tokenizer not available locally")

    result = QwenLossMasker.process_example(sample_sft_example, tokenizer=tok)
    labels = result["labels"]
    input_ids = result["input_ids"]
    assert len(labels) == len(input_ids)

    # Decode unmasked tokens (where label != -100)
    unmasked_ids = [tid for tid, lab in zip(input_ids, labels) if lab != IGNORE_INDEX]
    unmasked_text = tok.decode(unmasked_ids)

    # Unmasked text MUST contain assistant tool call and assistant response
    assert "lookup_order" in unmasked_text
    assert "shipped and on the way" in unmasked_text

    # Unmasked text MUST NOT contain system prompt instructions or raw user question
    assert "You are a helpful customer support assistant" not in unmasked_text
    assert "Where is my order ORD-501?" not in unmasked_text

    # End of turn token <|im_end|> must be unmasked
    assert IM_END in unmasked_text or tok.eos_token in unmasked_text


def test_loss_masking_thinking_mode():
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B", trust_remote_code=True)
    except Exception:
        pytest.skip("Qwen tokenizer not available locally")

    text = (
        f"{IM_START}system\nHelpful assistant.{IM_END}\n"
        f"{IM_START}user\nCalculate refund{IM_END}\n"
        f"{IM_START}assistant\n"
        f"<think>\nCalculating 100 minus 40 equals 60.\n</think>\n"
        f"Your refund is $60.00.{IM_END}"
    )
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    input_ids = enc["input_ids"]
    offsets = enc["offset_mapping"]

    # Test 1: Thinking tokens masked
    labels_masked = QwenLossMasker.mask_with_offsets(text, input_ids, offsets, mask_think_tokens=True)
    unmasked_ids_masked = [tid for tid, lab in zip(input_ids, labels_masked) if lab != IGNORE_INDEX]
    unmasked_text_masked = tok.decode(unmasked_ids_masked)
    assert "Calculating 100 minus 40" not in unmasked_text_masked
    assert "$60.00" in unmasked_text_masked

    # Test 2: Thinking tokens kept
    labels_kept = QwenLossMasker.mask_with_offsets(text, input_ids, offsets, mask_think_tokens=False)
    unmasked_ids_kept = [tid for tid, lab in zip(input_ids, labels_kept) if lab != IGNORE_INDEX]
    unmasked_text_kept = tok.decode(unmasked_ids_kept)
    assert "Calculating 100 minus 40" in unmasked_text_kept
    assert "$60.00" in unmasked_text_kept


def test_truncation_enforcement(sample_sft_example):
    # Cap seq length at 25 tokens
    result = QwenLossMasker.process_example(sample_sft_example, tokenizer=None, max_seq_length=25)
    assert result["truncated"] is True
    assert len(result["input_ids"]) == 25
    assert len(result["labels"]) == 25
