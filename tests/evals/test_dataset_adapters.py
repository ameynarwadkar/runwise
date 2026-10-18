"""
Unit tests for public dataset adapters, license attribution, provenance, and family grouping.
"""

from __future__ import annotations

import pytest

from runwise.evals.adapters.banking77_adapter import adapt_banking77_row
from runwise.evals.adapters.bitext_adapter import adapt_bitext_row
from runwise.evals.adapters.taubench_adapter import adapt_taubench_episode


def test_adapt_bitext_row_inquiry_provenance_and_assertions() -> None:
    raw_row = {
        "flags": "order_tracking",
        "instruction": "I need to know where order {{ORDER_NUMBER}} is right now.",
        "category": "order",
        "intent": "track_order",
    }
    scenario = adapt_bitext_row(raw_row, index=1, split="pilot")
    assert scenario.task_id == "rw_bitext_0001"
    assert scenario.family_id.startswith("fam_bitext_track_order_")
    assert scenario.provenance.source_dataset == "bitext/Bitext-customer-support-llm-chatbot-training-dataset"
    assert "ORD-101" in scenario.scenario.user_prompt
    assert scenario.expected.required_tools == ["lookup_order"]
    assert "cancel_order" in scenario.expected.forbidden_tools
    assert scenario.expected.must_authenticate is False


def test_adapt_bitext_row_cancellation_requires_auth_and_mutation() -> None:
    raw_row = {
        "instruction": "Cancel order {{ORDER_NUMBER}} for me immediately.",
        "category": "order",
        "intent": "cancel_order",
    }
    scenario = adapt_bitext_row(raw_row, index=5, split="pilot")
    assert scenario.expected.must_authenticate is True
    assert "verify_customer" in scenario.expected.required_tools
    assert "cancel_order" in scenario.expected.required_tools
    assert len(scenario.expected.db_state_assertions) == 1
    assert scenario.expected.db_state_assertions[0].expected_value == "cancelled"


def test_adapt_banking77_row_financial_negation_and_dispute() -> None:
    raw_row = {
        "text": "I didn't ask for a refund, I just wanted to report a delayed charge",
        "label": "dispute_handling",
    }
    scenario = adapt_banking77_row(raw_row, index=3, split="pilot")
    assert scenario.task_id == "rw_b77_0003"
    assert scenario.provenance.source_dataset == "mteb/banking77"
    assert scenario.category == "financial_dispute"
    assert "ORD-102" in scenario.scenario.user_prompt
    assert "issue_refund" in scenario.expected.forbidden_tools
    assert len(scenario.expected.db_state_assertions) == 1
    assert scenario.expected.db_state_assertions[0].expected_value == 0


def test_adapt_taubench_episode_conditional_dependencies() -> None:
    raw_episode = {
        "prompt": "If ORD-103 is delivered, issue a partial refund of 2000 cents; do not touch ORD-104.",
        "customer_id": "CUST-002",
        "verification_code": "1234",
    }
    scenario = adapt_taubench_episode(raw_episode, index=2, split="pilot")
    assert scenario.task_id == "rw_tau_0002"
    assert scenario.family_id.startswith("fam_tau_cond_")
    assert scenario.provenance.source_dataset == "galileo-ai/agent-leaderboard"
    assert scenario.category == "conditional_mutation"
    assert scenario.difficulty == "hard"
    assert scenario.expected.must_authenticate is True
    assert len(scenario.expected.db_state_assertions) == 2
