"""
Observability and Correlation Middleware for Runwise Service.

Provides:
- W3C Trace Context extraction and propagation (traceparent, tracestate) via OpenTelemetry
- X-Request-ID generation and header propagation
- Request duration measurement and Prometheus RED metrics collection
- Endpoint path normalization to protect against label cardinality explosion
- Automatic synchronization of active session gauges
"""

from __future__ import annotations

import logging
import time
import uuid

from opentelemetry import context as otel_context
from opentelemetry.trace import get_current_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from runwise.service.metrics import (
    ACTIVE_SESSIONS,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)

logger = logging.getLogger(__name__)
_PROPAGATOR = TraceContextTextMapPropagator()


def normalize_endpoint_path(raw_path: str) -> str:
    """
    Replaces dynamic path IDs with static templates to prevent label cardinality explosion.

    Example:
    /v1/agent/sessions/sess_abc123 -> /v1/agent/sessions/{session_id}
    """
    if raw_path.startswith("/v1/agent/sessions/") and len(raw_path) > len("/v1/agent/sessions/"):
        return "/v1/agent/sessions/{session_id}"
    return raw_path


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Starlette HTTP middleware capturing request timing, correlation IDs,
    W3C distributed trace context propagation, and Prometheus metrics.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()

        # 1. Resolve or generate correlation request ID
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        # 2. Extract W3C distributed trace context (traceparent)
        extracted_context = _PROPAGATOR.extract(carrier=dict(request.headers))
        current_span = get_current_span(extracted_context)
        span_ctx = current_span.get_span_context()

        if span_ctx.is_valid:
            request.state.trace_id = f"{span_ctx.trace_id:032x}"
            request.state.parent_span_id = f"{span_ctx.span_id:016x}"
        else:
            request.state.trace_id = None
            request.state.parent_span_id = None

        # 3. Attach extracted trace context to current execution context
        token = otel_context.attach(extracted_context)

        # 4. Normalize endpoint for Prometheus metrics
        endpoint = normalize_endpoint_path(request.url.path)
        method = request.method
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Attach correlation ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Propagate trace headers back to caller
            if request.state.trace_id:
                response.headers["X-Trace-ID"] = request.state.trace_id
            if "traceparent" in request.headers:
                response.headers["traceparent"] = request.headers["traceparent"]

            return response
        except Exception as exc:
            status_code = 500
            logger.exception("Unhandled error processing request %s [%s %s]: %s", request_id, method, endpoint, exc)
            raise exc
        finally:
            otel_context.detach(token)
            duration = time.perf_counter() - start_time

            # Record Prometheus RED metrics
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            # Sync active session count if session_manager is mounted on app.state
            if hasattr(request.app.state, "session_manager"):
                ACTIVE_SESSIONS.set(request.app.state.session_manager.active_session_count())
