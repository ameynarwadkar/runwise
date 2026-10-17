"""
End-to-end integration tests for the Runwise Observability and Telemetry stack.

Verifies:
- Distributed trace propagation across HTTP headers and OpenTelemetry spans.
- OpenTelemetry parent-child span hierarchy and request correlation linking.
- Prometheus metrics exposition across endpoints (/metrics).
- Agent run, token usage, and tool execution metrics in scrape output.
- Active session gauge lifecycle synchronization with SessionManager.
- Model gateway reliability telemetry (retries, fallbacks) in Prometheus metrics.
- Service readiness probe (/readyz) database failure degradation.
"""

import sqlite3
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from runwise.service.app import create_app
from runwise.service.gateway import ModelGateway
from runwise.service.session import SessionManager


def _make_mock_response(
    content: str | None = None,
    tool_calls: list | None = None,
    model: str = "mock-obs-model",
) -> SimpleNamespace:
    """Helper creating a mocked LLM response."""
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(prompt_tokens=45, completion_tokens=15, total_tokens=60)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


def _make_tool_call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    """Helper creating a mocked tool call object."""
    func = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, function=func)


def test_end_to_end_distributed_trace_propagation():
    """
    Verify complete distributed trace context flow:
    - Client sends W3C traceparent and X-Request-ID.
    - ObservabilityMiddleware extracts trace context and propagates headers in response.
    - OpenTelemetry captures agent_run span with client's trace ID and parent span ID.
    - Span attributes contain http.request_id.
    """
    exporter = InMemorySpanExporter()
    current_provider = trace.get_tracer_provider()
    if hasattr(current_provider, "add_span_processor"):
        current_provider.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)


    mock_resp = _make_mock_response("I am ready to help.")
    gateway = ModelGateway(
        primary_model="mock-trace-model",
        completion_fn=lambda **kwargs: mock_resp,
    )
    app = create_app(gateway=gateway)
    client = TestClient(app)

    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    parent_id = "00f067aa0ba902b7"
    traceparent = f"00-{trace_id}-{parent_id}-01"
    request_id = "req_e2e_trace_obs_123"

    response = client.post(
        "/v1/agent/run",
        json={"prompt": "Hello support", "task_id": "e2e_trace_task"},
        headers={
            "traceparent": traceparent,
            "X-Request-ID": request_id,
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    assert response.headers["X-Trace-ID"] == trace_id
    assert response.headers["traceparent"] == traceparent

    spans = exporter.get_finished_spans()
    assert len(spans) >= 1

    # Locate the root agent_run span
    agent_spans = [s for s in spans if s.name == "agent_run:e2e_trace_task"]
    assert len(agent_spans) == 1
    root_span = agent_spans[0]

    assert f"{root_span.context.trace_id:032x}" == trace_id
    assert f"{root_span.parent.span_id:016x}" == parent_id
    assert root_span.attributes.get("http.request_id") == request_id


def test_prometheus_metrics_scrape_endpoint():
    """Verify GET /metrics returns valid Prometheus exposition text."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text = response.text
    assert "runwise_http_requests_total" in text
    assert "runwise_http_request_duration_seconds" in text


def test_agent_execution_metrics_in_scrape():
    """Verify single-turn agent execution records model name, run count, and token metrics."""
    mock_resp = _make_mock_response("Welcome to customer support!", model="mock-metrics-model")
    gateway = ModelGateway(
        primary_model="mock-metrics-model",
        completion_fn=lambda **kwargs: mock_resp,
    )
    app = create_app(gateway=gateway)
    client = TestClient(app)

    response = client.post(
        "/v1/agent/run",
        json={"prompt": "Hello", "task_id": "test_scrape_run"},
    )
    assert response.status_code == 200

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    text = metrics_resp.text

    assert "runwise_agent_runs_total" in text
    assert "NORMAL_COMPLETION" in text
    assert "mock-metrics-model" in text
    assert "runwise_agent_tokens_total" in text
    assert 'token_type="prompt"' in text
    assert 'token_type="completion"' in text


def test_tool_dispatch_metrics_in_scrape():
    """Verify that domain tool executions record granular tool call metrics."""
    tc = _make_tool_call(
        "call_auth_obs",
        "verify_customer",
        {"user_id": "CUST-001", "verification_code": "1234"},
    )
    turn1_tc = _make_mock_response(content=None, tool_calls=[tc], model="mock-tool-model")
    turn1_final = _make_mock_response(content="Customer verified.", model="mock-tool-model")
    mock_queue = [turn1_tc, turn1_final]

    gateway = ModelGateway(
        primary_model="mock-tool-model",
        completion_fn=lambda **kwargs: mock_queue.pop(0),
    )
    app = create_app(gateway=gateway)
    client = TestClient(app)

    response = client.post(
        "/v1/agent/run",
        json={"prompt": "Verify customer CUST-001", "task_id": "test_tool_scrape"},
    )
    assert response.status_code == 200

    metrics_resp = client.get("/metrics")
    text = metrics_resp.text
    assert "runwise_agent_tool_calls_total" in text
    assert "verify_customer" in text
    assert "success" in text


def test_session_active_gauge_lifecycle_via_api():
    """Verify runwise_active_sessions gauge synchronizes with session creation and deletion."""
    session_manager = SessionManager()
    mock_resp = _make_mock_response("Hello")
    gateway = ModelGateway(completion_fn=lambda **kwargs: mock_resp)
    app = create_app(session_manager=session_manager, gateway=gateway)
    client = TestClient(app)

    session_id = "sess_obs_lifecycle"

    # 1. Start session
    r1 = client.post(
        "/v1/agent/run",
        json={"prompt": "Hi", "session_id": session_id},
    )
    assert r1.status_code == 200

    # Verify gauge updated to 1
    m1 = client.get("/metrics")
    assert "runwise_active_sessions 1.0" in m1.text

    # Verify readyz confirms 1 active session
    ready_resp = client.get("/readyz")
    assert ready_resp.json()["active_sessions"] == 1

    # 2. Terminate session
    del_resp = client.delete(f"/v1/agent/sessions/{session_id}")
    assert del_resp.status_code == 200

    # Verify gauge updated to 0
    m2 = client.get("/metrics")
    assert "runwise_active_sessions 0.0" in m2.text

    ready_resp2 = client.get("/readyz")
    assert ready_resp2.json()["active_sessions"] == 0


def test_readiness_probe_database_failure():
    """Verify /readyz returns HTTP 503 when the database sandbox check fails."""
    app = create_app()
    client = TestClient(app)

    with patch("runwise.service.app.SandboxDB.create_connection", side_effect=sqlite3.OperationalError("disk failure")):
        response = client.get("/readyz")
        assert response.status_code == 503
        data = response.json()
        assert "Database sandbox check failed" in data["detail"]


def test_gateway_retry_and_fallback_prometheus_metrics():
    """Verify gateway retries and fallback events increment Prometheus counters."""
    def mock_completion(**kwargs: Any) -> Any:
        model = kwargs.get("model", "")
        # Robust substring check accounting for provider prefix (e.g. vertex_ai/...)
        if "failing-primary-obs" in model:
            err = Exception("Rate limit exceeded 429")
            setattr(err, "status_code", 429)
            raise err
        return _make_mock_response("Fallback succeeded", model="working-fallback-obs")

    gateway = ModelGateway(
        primary_model="failing-primary-obs",
        fallback_model="working-fallback-obs",
        max_retries=1,
        base_delay_seconds=0.01,
        completion_fn=mock_completion,
    )
    app = create_app(gateway=gateway)
    client = TestClient(app)

    response = client.post(
        "/v1/agent/run",
        json={"prompt": "Hello fallback", "task_id": "test_gateway_metrics"},
    )
    assert response.status_code == 200

    metrics_resp = client.get("/metrics")
    text = metrics_resp.text

    assert "runwise_gateway_retries_total" in text
    assert "failing-primary-obs" in text
    assert "rate_limit_429" in text
    assert "runwise_gateway_fallbacks_total" in text
    assert "working-fallback-obs" in text
