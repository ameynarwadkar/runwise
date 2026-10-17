"""
Unit tests for the Runwise HTTP service Pydantic schemas.
"""

import pytest
from pydantic import ValidationError

from runwise.service.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    HealthResponse,
    TokenUsageSchema,
)


def test_health_response_defaults():
    """Verify HealthResponse populates valid default values and ISO timestamp."""
    resp = HealthResponse()
    assert resp.status == "ok"
    assert resp.version == "0.1.0"
    assert "T" in resp.timestamp


def test_agent_run_request_defaults():
    """Verify AgentRunRequest generates an automatic session_id and trims whitespace."""
    req = AgentRunRequest(prompt="  Where is my order ORD-101?  ")
    assert req.prompt == "Where is my order ORD-101?"
    assert req.session_id.startswith("sess_")
    assert req.customer_id is None
    assert req.task_id == "adhoc_api_run"


def test_agent_run_request_empty_prompt_rejection():
    """Verify that empty or whitespace-only prompts raise a ValidationError."""
    with pytest.raises(ValidationError):
        AgentRunRequest(prompt="")

    with pytest.raises(ValidationError):
        AgentRunRequest(prompt="   \n\t  ")


def test_agent_run_response_serialization():
    """Verify serialization of AgentRunResponse into a JSON-compatible dict."""
    resp = AgentRunResponse(
        session_id="sess_12345",
        response="Your order ORD-101 has shipped.",
        exit_reason="final_response",
        step_count=2,
        tokens=TokenUsageSchema(prompt_tokens=120, completion_tokens=35, total_tokens=155),
        latency_ms=452.8,
        model="gemini/gemini-2.5-flash",
        prompt_version="v1.0",
    )
    dumped = resp.model_dump()
    assert dumped["session_id"] == "sess_12345"
    assert dumped["tokens"]["total_tokens"] == 155
    assert dumped["step_count"] == 2
    assert dumped["latency_ms"] == 452.8
    assert dumped["model"] == "gemini/gemini-2.5-flash"
