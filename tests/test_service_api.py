"""
End-to-end integration tests for the Runwise FastAPI Service endpoints.

Verifies:
- Liveness health probe (/healthz)
- Readiness probe (/readyz)
- Prometheus metrics endpoint (/metrics)
- Single-turn agent execution with metrics emission (/v1/agent/run)
- Multi-turn session persistence and authentication context
- Input validation rejection on empty queries
- Session deletion and cleanup (/v1/agent/sessions/{session_id})
"""

from types import SimpleNamespace
from typing import Any
import pytest
from fastapi.testclient import TestClient

from runwise.service.app import create_app
from runwise.service.gateway import ModelGateway
from runwise.service.session import SessionManager


def _make_mock_response(content: str | None = None, tool_calls: list | None = None) -> SimpleNamespace:
    """Helper creating an object mirroring LiteLLM/OpenAI completion responses."""
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(prompt_tokens=40, completion_tokens=15, total_tokens=55)
    return SimpleNamespace(choices=[choice], usage=usage, model="mock-model")


def _make_tool_call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    """Helper creating a mocked tool call object."""
    func = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, function=func)


def test_healthz_endpoint():
    """Verify GET /healthz returns 200 OK with valid service metadata."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert "X-Request-ID" in response.headers


def test_readyz_endpoint():
    """Verify GET /readyz returns 200 OK and confirms database/provider readiness."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ready"
    assert "provider" in data
    assert "model" in data


def test_metrics_endpoint():
    """Verify GET /metrics returns Prometheus formatted scrape text."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text = response.text
    assert "runwise_http_requests_total" in text


def test_agent_run_emits_telemetry_metrics():
    """Verify POST /v1/agent/run executes single turn and updates Prometheus metrics."""
    mock_resp = _make_mock_response("Hello! How can I assist you with your order?")
    gateway = ModelGateway(
        primary_model="mock-telemetry-model",
        completion_fn=lambda **kwargs: mock_resp,
    )
    app = create_app(gateway=gateway)
    client = TestClient(app)

    payload = {
        "prompt": "Hello",
        "task_id": "test_telemetry_turn",
    }
    response = client.post("/v1/agent/run", json=payload)
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers

    # Check metrics endpoint to ensure runwise_agent_runs_total was recorded
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    metrics_text = metrics_resp.text
    assert "runwise_agent_runs_total" in metrics_text
    assert "mock-telemetry-model" in metrics_text


def test_agent_run_multi_turn_session_persistence():
    """
    Verify multi-turn state persistence across sequential HTTP requests:
    - Turn 1: Agent calls verify_customer tool, authenticating the session.
    - Turn 2: Agent checks order status for the authenticated customer in the same sandbox.
    """
    # Turn 1: Model calls verify_customer tool, then returns confirmation
    tc = _make_tool_call(
        "call_auth_1",
        "verify_customer",
        {"user_id": "CUST-001", "verification_code": "1234"},
    )
    turn1_tc = _make_mock_response(content=None, tool_calls=[tc])
    turn1_final = _make_mock_response(content="You have been verified as Alice Smith.")
    turn2_final = _make_mock_response(content="Your order ORD-101 is pending delivery.")

    mock_queue = [turn1_tc, turn1_final, turn2_final]

    def mock_completion(**kwargs: Any) -> Any:
        return mock_queue.pop(0)

    session_manager = SessionManager()
    gateway = ModelGateway(
        primary_model="mock-model",
        completion_fn=mock_completion,
    )
    app = create_app(session_manager=session_manager, gateway=gateway)
    client = TestClient(app)

    session_id = "sess_customer_alice"

    # Turn 1 request
    r1 = client.post(
        "/v1/agent/run",
        json={
            "prompt": "Verify me as CUST-001 with alice@example.com",
            "session_id": session_id,
        },
    )
    assert r1.status_code == 200
    assert r1.json()["response"] == "You have been verified as Alice Smith."

    # Verify underlying session context in SessionManager retained authentication
    context = session_manager.get(session_id)
    assert context is not None
    assert context.authenticated_user_id == "CUST-001"

    # Turn 2 request reusing same session_id
    r2 = client.post(
        "/v1/agent/run",
        json={
            "prompt": "Where is my order?",
            "session_id": session_id,
        },
    )
    assert r2.status_code == 200
    assert r2.json()["response"] == "Your order ORD-101 is pending delivery."


def test_agent_run_validation_rejection():
    """Verify POST /v1/agent/run rejects empty or whitespace-only prompts with HTTP 422."""
    app = create_app()
    client = TestClient(app)

    response = client.post("/v1/agent/run", json={"prompt": "    "})
    assert response.status_code == 422


def test_session_lifecycle_termination_endpoint():
    """Verify DELETE /v1/agent/sessions/{session_id} terminates session and releases DB."""
    mock_resp = _make_mock_response("Hello")
    gateway = ModelGateway(completion_fn=lambda **kwargs: mock_resp)
    session_manager = SessionManager()
    app = create_app(session_manager=session_manager, gateway=gateway)
    client = TestClient(app)

    session_id = "sess_to_delete"

    # 1. Create active session
    client.post("/v1/agent/run", json={"prompt": "Hi", "session_id": session_id})
    assert session_manager.active_session_count() == 1

    # 2. Terminate session via API
    del_resp = client.delete(f"/v1/agent/sessions/{session_id}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"status": "terminated", "session_id": session_id}
    assert session_manager.active_session_count() == 0

    # 3. Subsequent termination returns 404 Not Found
    del_again = client.delete(f"/v1/agent/sessions/{session_id}")
    assert del_again.status_code == 404
