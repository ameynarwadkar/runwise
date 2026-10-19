"""
Unit tests for QwenAdapter, QwenToolCallParser, and AgentLoop integration.
"""

import json
from pathlib import Path
import pytest
from runwise.agent.adapters.qwen_adapter import (
    QwenAdapter,
    QwenToolCallParser,
    format_qwen_chat,
    parse_qwen_tool_calls,
)
from runwise.agent.loop import AgentLoop
from runwise.agent.trajectory import ExitReason
from runwise.domain.model import SessionContext
from runwise.domain.db import SandboxDB


def test_parser_extracts_tool_calls_and_thinking():
    raw_output = (
        "<think>\n"
        "Customer wants to look up order ORD-501. I should call lookup_order.\n"
        "</think>\n"
        "I am checking that for you.\n"
        "<tool_call>\n"
        '{"name": "lookup_order", "arguments": {"order_id": "ORD-501"}}\n'
        "</tool_call>"
    )
    cleaned_content, tool_calls, think_content = parse_qwen_tool_calls(raw_output)

    assert think_content == "Customer wants to look up order ORD-501. I should call lookup_order."
    assert cleaned_content == "I am checking that for you."
    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["name"] == "lookup_order"
    args = json.loads(tool_calls[0]["function"]["arguments"])
    assert args["order_id"] == "ORD-501"


def test_parser_handles_multiple_tool_calls():
    raw_output = (
        "<tool_call>\n"
        '{"name": "lookup_order", "arguments": {"order_id": "ORD-501"}}\n'
        "</tool_call>\n"
        "<tool_call>\n"
        '{"name": "lookup_policy", "arguments": {"topic": "cancellations"}}\n'
        "</tool_call>"
    )
    cleaned_content, tool_calls, think_content = parse_qwen_tool_calls(raw_output)
    assert think_content is None
    assert cleaned_content == ""
    assert len(tool_calls) == 2
    assert tool_calls[0]["function"]["name"] == "lookup_order"
    assert tool_calls[1]["function"]["name"] == "lookup_policy"


def test_parser_ignores_malformed_tool_call_json():
    raw_output = (
        "Here is invalid xml:\n"
        "<tool_call>\n"
        "{bad json payload}\n"
        "</tool_call>\n"
        "Some normal text."
    )
    cleaned_content, tool_calls, think_content = parse_qwen_tool_calls(raw_output)
    assert len(tool_calls) == 0
    assert "Some normal text." in cleaned_content


def test_parser_strips_residual_special_tokens():
    raw_output_tool = (
        "<tool_call>\n"
        '{"name": "lookup_order", "arguments": {"order_id": "ORD-501"}}\n'
        "</tool_call><|im_end|>"
    )
    cleaned_tool, tool_calls, think = parse_qwen_tool_calls(raw_output_tool)
    assert len(tool_calls) == 1
    assert cleaned_tool == ""

    raw_output_text = "I am processing your cancellation.<|im_end|>"
    cleaned_text, tool_calls, think = parse_qwen_tool_calls(raw_output_text)
    assert cleaned_text == "I am processing your cancellation."

    raw_output_mixed = "<|im_start|>assistant\nYour order is delivered.<|endoftext|>"
    cleaned_mixed, tool_calls, think = parse_qwen_tool_calls(raw_output_mixed)
    assert cleaned_mixed == "Your order is delivered."


def test_format_qwen_chat():
    messages = [
        {"role": "system", "content": "You are a customer support agent."},
        {"role": "user", "content": "Where is my order ORD-501?"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {"name": "lookup_order", "arguments": {"order_id": "ORD-501"}},
                }
            ],
        },
        {"role": "tool", "content": '{"status": "shipped"}'},
    ]
    tools = [
        {"type": "function", "function": {"name": "lookup_order", "parameters": {"type": "object"}}}
    ]
    chat_str = format_qwen_chat(messages, tools=tools)
    assert "<|im_start|>system" in chat_str
    assert "<tools>" in chat_str
    assert "lookup_order" in chat_str
    assert "<|im_start|>user\nWhere is my order ORD-501?<|im_end|>" in chat_str
    assert "<tool_call>" in chat_str
    assert "<tool_response>" in chat_str


def test_qwen_adapter_complete_agent_loop_integration():
    # Mock generation function for QwenAdapter
    def mock_generate(prompt: str) -> str:
        if "<tool_response>" not in prompt:
            # Turn 1: call lookup_order
            return (
                "<think>Need to look up ORD-501</think>\n"
                "<tool_call>\n"
                '{"name": "lookup_order", "arguments": {"order_id": "ORD-501"}}\n'
                "</tool_call>"
            )
        else:
            # Turn 2: final answer
            return "Order ORD-501 is currently pending."

    adapter = QwenAdapter(generate_fn=mock_generate, model_name="Qwen/Qwen3-1.7B")

    conn = SandboxDB.create_connection()
    session = SessionContext(conn=conn, trial_id="trial_qwen_adapter", current_time_iso="2026-10-15T12:00:00Z")

    loop = AgentLoop(gateway=adapter)
    traj = loop.run(
        user_prompt="Status of ORD-501?",
        session=session,
        task_id="task_qwen_integration",
    )

    assert traj.exit_reason == ExitReason.NORMAL_COMPLETION
    assert traj.final_response == "Order ORD-501 is currently pending."

    # Verify tool events in trajectory
    tool_events = [e for e in traj.events if e.event_type == "TOOL_RESULT"]
    assert len(tool_events) == 1
    assert "lookup_order" in tool_events[0].content

    conn.close()
