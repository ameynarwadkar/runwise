"""
Pydantic data models for Supervised Fine-Tuning (SFT) conversation traces,
structured tool calls, and dataset quality metadata.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class FunctionCall(BaseModel):
    """Function call payload with name and arguments."""
    name: str
    arguments: dict[str, Any] | str


class ToolCall(BaseModel):
    """Standard OpenAI-compatible tool call definition."""
    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


class ConversationMessage(BaseModel):
    """Single turn in a multi-turn conversation trace."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class SFTExample(BaseModel):
    """
    Complete canonical SFT training example grounded in real domain tool execution.
    """
    example_id: str
    curriculum_domain: Literal[
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
    difficulty: Literal["easy", "medium", "hard"]
    customer_id: str
    order_id: str | None = None
    scenario_prompt: str
    tools: list[dict[str, Any]]
    messages: list[ConversationMessage]
    metadata: dict[str, Any] = Field(default_factory=dict)
    ground_truth_db_assertions: list[dict[str, Any]] = Field(default_factory=list)
