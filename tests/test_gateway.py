"""
Unit tests for ModelGateway: verifies timeouts, exponential retries on 429/5xx,
fail-fast on 400 errors, and automated fallback to secondary model.
"""

from types import SimpleNamespace
from typing import Any
import pytest

from runwise.agent.loop import AgentLoop
from runwise.agent.trajectory import ExitReason
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext
from runwise.service.gateway import ModelGateway


def _make_mock_response(content: str = "Success", model: str = "mock-model") -> SimpleNamespace:
    """Helper creating a LiteLLM-like completion response."""
    msg = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


def test_gateway_happy_path_primary():
    """Verify primary model succeeds cleanly on first attempt."""
    mock_resp = _make_mock_response("Order is shipped")

    def mock_completion(**kwargs: Any) -> Any:
        assert kwargs["model"] == "primary-model"
        assert kwargs["timeout"] == 15.0
        return mock_resp

    gateway = ModelGateway(
        primary_model="primary-model",
        fallback_model="fallback-model",
        timeout_seconds=15.0,
        completion_fn=mock_completion,
    )

    resp = gateway.complete(messages=[{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "Order is shipped"
    assert gateway.stats.total_requests == 1
    assert gateway.stats.successful_requests == 1
    assert gateway.stats.retry_count == 0
    assert gateway.stats.fallback_count == 0


def test_gateway_retries_on_transient_error_and_succeeds():
    """Verify gateway retries when encountering a 429 and succeeds on next attempt."""
    attempts = 0

    def mock_completion(**kwargs: Any) -> Any:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            # Simulate a 429 RateLimit error
            err = Exception("Rate limit exceeded 429")
            setattr(err, "status_code", 429)
            raise err
        return _make_mock_response("Recovered after 429")

    gateway = ModelGateway(
        primary_model="primary-model",
        max_retries=2,
        base_delay_seconds=0.01,  # Fast backoff for tests
        completion_fn=mock_completion,
    )

    resp = gateway.complete(messages=[{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "Recovered after 429"
    assert attempts == 2
    assert gateway.stats.retry_count == 1
    assert gateway.stats.successful_requests == 1


def test_gateway_fails_fast_on_bad_request():
    """Verify gateway never retries a 400 client error."""
    attempts = 0

    def mock_completion(**kwargs: Any) -> Any:
        nonlocal attempts
        attempts += 1
        err = Exception("Bad request: invalid schema")
        setattr(err, "status_code", 400)
        raise err

    gateway = ModelGateway(
        primary_model="primary-model",
        max_retries=3,
        base_delay_seconds=0.01,
        completion_fn=mock_completion,
    )

    with pytest.raises(Exception) as exc_info:
        gateway.complete(messages=[{"role": "user", "content": "hi"}])

    assert "Bad request" in str(exc_info.value)
    # Must fail on attempt 1 without retries
    assert attempts == 1
    assert gateway.stats.retry_count == 0
    assert gateway.stats.failed_requests == 1


def test_gateway_falls_back_when_primary_exhausted():
    """Verify gateway switches to fallback model after primary retries are exhausted."""
    primary_attempts = 0
    fallback_attempts = 0

    def mock_completion(**kwargs: Any) -> Any:
        nonlocal primary_attempts, fallback_attempts
        model = kwargs["model"]
        if model == "primary-model":
            primary_attempts += 1
            err = Exception("Primary unavailable 503")
            setattr(err, "status_code", 503)
            raise err
        elif model == "fallback-model":
            fallback_attempts += 1
            return _make_mock_response("Served from fallback", model="fallback-model")
        raise ValueError(f"Unexpected model: {model}")

    gateway = ModelGateway(
        primary_model="primary-model",
        fallback_model="fallback-model",
        max_retries=1,  # 1 initial + 1 retry = 2 primary attempts
        base_delay_seconds=0.01,
        completion_fn=mock_completion,
    )

    resp = gateway.complete(messages=[{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "Served from fallback"
    assert primary_attempts == 2
    assert fallback_attempts == 1
    assert gateway.stats.fallback_count == 1
    assert gateway.stats.successful_requests == 1


def test_agent_loop_integration_with_gateway():
    """Verify AgentLoop routes through ModelGateway when provided."""
    mock_resp = _make_mock_response("Hello from gateway-managed agent!")

    def mock_completion(**kwargs: Any) -> Any:
        return mock_resp

    gateway = ModelGateway(
        primary_model="primary-model",
        completion_fn=mock_completion,
    )

    conn = SandboxDB.create_connection()
    session = SessionContext(conn=conn, trial_id="trial_gw", current_time_iso="2026-10-15T12:00:00Z")

    agent = AgentLoop(model="primary-model", gateway=gateway)
    trajectory = agent.run(user_prompt="Hello", session=session)

    assert trajectory.exit_reason == ExitReason.NORMAL_COMPLETION
    assert trajectory.final_response == "Hello from gateway-managed agent!"
    assert gateway.stats.successful_requests == 1
