"""
Unit tests for ObservabilityMiddleware: verifies correlation IDs, Prometheus
metrics collection, path normalization, W3C traceparent propagation, and error handling.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from runwise.service.metrics import get_metrics_payload
from runwise.service.middleware import ObservabilityMiddleware, normalize_endpoint_path


def _create_test_app() -> FastAPI:
    """Helper creating a minimal test app wrapped in ObservabilityMiddleware."""
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/test/hello")
    def hello():
        return {"message": "hello"}

    @app.get("/v1/agent/sessions/{session_id}")
    def get_session(session_id: str):
        return {"session_id": session_id}

    @app.get("/test/error")
    def fail():
        raise RuntimeError("Simulated internal error")

    return app


def test_path_normalization():
    """Verify normalize_endpoint_path masks dynamic session IDs."""
    assert normalize_endpoint_path("/v1/agent/sessions/sess_9999") == "/v1/agent/sessions/{session_id}"
    assert normalize_endpoint_path("/healthz") == "/healthz"
    assert normalize_endpoint_path("/v1/agent/run") == "/v1/agent/run"


def test_middleware_generates_request_id_if_missing():
    """Verify middleware injects X-Request-ID into response if client omitted it."""
    app = _create_test_app()
    client = TestClient(app)

    response = client.get("/test/hello")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"].startswith("req_")


def test_middleware_preserves_client_request_id():
    """Verify middleware preserves client-supplied X-Request-ID."""
    app = _create_test_app()
    client = TestClient(app)

    custom_id = "client-trace-12345"
    response = client.get("/test/hello", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id


def test_middleware_records_normalized_prometheus_metrics():
    """Verify metrics record normalized path rather than dynamic session ID."""
    app = _create_test_app()
    client = TestClient(app)

    # Call with a unique session ID
    response = client.get("/v1/agent/sessions/sess_unique_test_123")
    assert response.status_code == 200

    payload, _ = get_metrics_payload()
    text = payload.decode("utf-8")

    # Metrics should contain the template, NOT the unique ID
    assert 'endpoint="/v1/agent/sessions/{session_id}"' in text
    assert "sess_unique_test_123" not in text


def test_middleware_captures_unhandled_exception_metric():
    """Verify middleware increments status 500 metric when an unhandled exception occurs."""
    app = _create_test_app()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/test/error")
    assert response.status_code == 500

    payload, _ = get_metrics_payload()
    text = payload.decode("utf-8")
    assert 'endpoint="/test/error",method="GET",status_code="500"' in text


def test_middleware_propagates_w3c_traceparent():
    """Verify middleware extracts W3C traceparent and attaches trace ID to response."""
    app = _create_test_app()
    client = TestClient(app)

    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    parent_id = "00f067aa0ba902b7"
    traceparent = f"00-{trace_id}-{parent_id}-01"

    response = client.get("/test/hello", headers={"traceparent": traceparent})
    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == trace_id
    assert response.headers["traceparent"] == traceparent


def test_distributed_trace_context_attaches_to_child_spans():
    """Verify child trace spans automatically inherit trace ID from HTTP traceparent header."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from runwise.observability.tracer import trace_span

    exporter = InMemorySpanExporter()
    current_provider = trace.get_tracer_provider()
    if hasattr(current_provider, "add_span_processor"):
        current_provider.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)


    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/test/traced_work")
    def traced_work():
        with trace_span("child_worker_span", attributes={"worker.task": "test"}) as span:
            span.set_output("done")
        return {"status": "ok"}

    client = TestClient(app)
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    parent_id = "00f067aa0ba902b7"
    traceparent = f"00-{trace_id}-{parent_id}-01"

    response = client.get("/test/traced_work", headers={"traceparent": traceparent})
    assert response.status_code == 200

    spans = exporter.get_finished_spans()
    assert len(spans) >= 1
    child_span = next(s for s in spans if s.name == "child_worker_span")
    assert f"{child_span.context.trace_id:032x}" == trace_id
    assert f"{child_span.parent.span_id:016x}" == parent_id
