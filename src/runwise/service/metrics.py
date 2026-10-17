"""
Prometheus Metrics Registry for the Runwise Production Agent Service.

Exports standard OpenTelemetry/Prometheus metrics for:
- HTTP traffic (rate, status codes, latency histograms)
- Agent execution (runs, reasoning latency, token consumption)
- Domain tools (dispatch count, success/error rates)
- Gateway reliability (retry rate, fallback rate)
- Active session memory footprint
"""

from __future__ import annotations

from typing import Any
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Standard latency buckets for web services and LLM agents (in seconds)
HTTP_LATENCY_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
AGENT_LATENCY_BUCKETS = (0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 30.0)

# ============================================================================
# HTTP SERVICE METRICS
# ============================================================================

HTTP_REQUESTS_TOTAL = Counter(
    "runwise_http_requests_total",
    "Total count of HTTP requests processed by the service.",
    labelnames=["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "runwise_http_request_duration_seconds",
    "HTTP request latency distribution in seconds.",
    labelnames=["method", "endpoint"],
    buckets=HTTP_LATENCY_BUCKETS,
)

# ============================================================================
# AGENT EXECUTION METRICS
# ============================================================================

AGENT_RUNS_TOTAL = Counter(
    "runwise_agent_runs_total",
    "Total agent reasoning turns and executions.",
    labelnames=["model", "exit_reason"],
)

AGENT_RUN_DURATION_SECONDS = Histogram(
    "runwise_agent_run_duration_seconds",
    "End-to-end agent execution latency in seconds.",
    labelnames=["model"],
    buckets=AGENT_LATENCY_BUCKETS,
)

AGENT_TOKENS_TOTAL = Counter(
    "runwise_agent_tokens_total",
    "Total tokens consumed by model calls, split by type.",
    labelnames=["model", "token_type"],  # token_type: 'prompt' or 'completion'
)

AGENT_TOOL_CALLS_TOTAL = Counter(
    "runwise_agent_tool_calls_total",
    "Total domain tool invocations executed by the agent.",
    labelnames=["tool_name", "status"],  # status: 'success' or 'error'
)

# ============================================================================
# GATEWAY RELIABILITY METRICS
# ============================================================================

GATEWAY_RETRIES_TOTAL = Counter(
    "runwise_gateway_retries_total",
    "Total model retry attempts triggered on transient 429/5xx errors.",
    labelnames=["model", "reason"],
)

GATEWAY_FALLBACKS_TOTAL = Counter(
    "runwise_gateway_fallbacks_total",
    "Total failover events from primary model to secondary fallback model.",
    labelnames=["primary_model", "fallback_model"],
)

# ============================================================================
# ACTIVE STATE METRICS
# ============================================================================

ACTIVE_SESSIONS = Gauge(
    "runwise_active_sessions",
    "Number of active in-memory customer support sandboxes currently managed.",
)

# ============================================================================
# CANARY & VARIANT TELEMETRY
# ============================================================================
CANARY_REQUESTS_TOTAL: Counter = Counter(
    "runwise_canary_requests_total",
    "Total requests processed partitioned by variant, model, and prompt version.",
    ["variant", "model", "prompt_version", "status"],
)

CANARY_LATENCY_SECONDS: Histogram = Histogram(
    "runwise_canary_latency_seconds",
    "Request execution latency in seconds partitioned by variant and model.",
    ["variant", "model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0),
)

# ============================================================================
# AUTO-ROUTING TELEMETRY
# ============================================================================
ROUTER_DECISIONS_TOTAL: Counter = Counter(
    "runwise_router_decisions_total",
    "Total requests classified and routed by the cost-aware AutoRouter.",
    ["selected_model", "risk_tier"],
)


def get_metrics_payload(registry: CollectorRegistry = REGISTRY) -> tuple[bytes, str]:
    """
    Serializes active metric collectors into standard Prometheus exposition format.

    Returns:
    --------
    tuple[bytes, str]: (payload_bytes, content_type_header)
    """
    return generate_latest(registry), CONTENT_TYPE_LATEST
