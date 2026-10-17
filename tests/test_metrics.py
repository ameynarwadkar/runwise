"""
Unit tests for Prometheus metrics registry in Runwise service.
"""

from runwise.service.metrics import (
    ACTIVE_SESSIONS,
    AGENT_RUN_DURATION_SECONDS,
    AGENT_RUNS_TOTAL,
    AGENT_TOKENS_TOTAL,
    AGENT_TOOL_CALLS_TOTAL,
    CONTENT_TYPE_LATEST,
    GATEWAY_FALLBACKS_TOTAL,
    GATEWAY_RETRIES_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    get_metrics_payload,
)
def test_metrics_serialization_and_content_type():
    """Verify that get_metrics_payload returns valid Prometheus payload and header."""
    payload, content_type = get_metrics_payload()
    assert isinstance(payload, bytes)
    assert content_type == CONTENT_TYPE_LATEST


def test_http_metrics_registration():
    """Verify HTTP requests counter and latency histogram increment correctly."""
    HTTP_REQUESTS_TOTAL.labels(method="POST", endpoint="/v1/agent/run", status_code="200").inc(3)
    HTTP_REQUEST_DURATION_SECONDS.labels(method="POST", endpoint="/v1/agent/run").observe(0.45)

    payload, _ = get_metrics_payload()
    text = payload.decode("utf-8")

    assert "runwise_http_requests_total" in text
    assert 'endpoint="/v1/agent/run"' in text
    assert 'method="POST"' in text
    assert "runwise_http_request_duration_seconds_bucket" in text


def test_agent_and_tool_metrics_registration():
    """Verify agent runs, token counts, and tool dispatch metrics increment cleanly."""
    AGENT_RUNS_TOTAL.labels(model="gemini-2.5-flash", exit_reason="NORMAL_COMPLETION").inc()
    AGENT_TOKENS_TOTAL.labels(model="gemini-2.5-flash", token_type="prompt").inc(1250)
    AGENT_TOKENS_TOTAL.labels(model="gemini-2.5-flash", token_type="completion").inc(180)
    AGENT_TOOL_CALLS_TOTAL.labels(tool_name="lookup_order", status="success").inc(2)

    payload, _ = get_metrics_payload()
    text = payload.decode("utf-8")

    assert 'runwise_agent_runs_total{exit_reason="NORMAL_COMPLETION",model="gemini-2.5-flash"}' in text
    assert 'runwise_agent_tokens_total{model="gemini-2.5-flash",token_type="prompt"}' in text
    assert 'runwise_agent_tool_calls_total{status="success",tool_name="lookup_order"}' in text


def test_gateway_reliability_metrics():
    """Verify gateway retries and fallback counters record correctly."""
    GATEWAY_RETRIES_TOTAL.labels(model="gemini-2.5-flash", reason="rate_limit_429").inc()
    GATEWAY_FALLBACKS_TOTAL.labels(
        primary_model="gemini-2.5-flash",
        fallback_model="gemini-2.0-flash",
    ).inc()

    payload, _ = get_metrics_payload()
    text = payload.decode("utf-8")

    assert 'runwise_gateway_retries_total{model="gemini-2.5-flash",reason="rate_limit_429"}' in text
    assert (
        'runwise_gateway_fallbacks_total{fallback_model="gemini-2.0-flash",primary_model="gemini-2.5-flash"}'
        in text
    )


def test_active_sessions_gauge():
    """Verify active sessions gauge updates value in-place."""
    ACTIVE_SESSIONS.set(14)
    payload, _ = get_metrics_payload()
    text = payload.decode("utf-8")

    assert "runwise_active_sessions 14.0" in text

    ACTIVE_SESSIONS.set(3)
    payload2, _ = get_metrics_payload()
    text2 = payload2.decode("utf-8")
    assert "runwise_active_sessions 3.0" in text2
