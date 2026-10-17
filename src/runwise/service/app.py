"""
FastAPI HTTP Application for the Runwise Production Agent Service.

Exposes endpoints for:
- Liveness health checks (/healthz)
- Readiness probes (/readyz)
- Prometheus metrics exposition (/metrics)
- Multi-turn customer support agent execution (/v1/agent/run)
- Session lifecycle management (/v1/agent/sessions/{session_id})
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status

from runwise.agent.loop import AgentLoop
from runwise.config import get_provider_config
from runwise.domain.db import SandboxDB
from runwise.service.gateway import ModelGateway
from runwise.service.metrics import (
    AGENT_RUN_DURATION_SECONDS,
    AGENT_RUNS_TOTAL,
    AGENT_TOKENS_TOTAL,
    AGENT_TOOL_CALLS_TOTAL,
    get_metrics_payload,
)
from runwise.service.middleware import ObservabilityMiddleware
from runwise.service.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    HealthResponse,
    TokenUsageSchema,
)
from runwise.service.session import SessionManager

logger = logging.getLogger(__name__)


def get_session_manager(request: Request) -> SessionManager:
    """FastAPI dependency resolving the active SessionManager instance."""
    return request.app.state.session_manager


def get_agent_loop(request: Request) -> AgentLoop:
    """FastAPI dependency resolving the active AgentLoop instance."""
    return request.app.state.agent_loop


def create_app(
    session_manager: SessionManager | None = None,
    gateway: ModelGateway | None = None,
    agent_loop: AgentLoop | None = None,
) -> FastAPI:
    """
    Application factory for constructing the Runwise FastAPI service.

    Allows injecting test dependencies or custom gateways during testing.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup: verify components are ready
        logger.info("Initializing Runwise Agent Service...")
        yield
        # Shutdown: close all active session databases
        logger.info("Shutting down Runwise Agent Service, releasing sandboxes...")
        app.state.session_manager.clear()

    app = FastAPI(
        title="Runwise Agent Service",
        description="Production Agent Service with isolated session sandboxing and gateway reliability.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 1. Mount Observability and Request Correlation Middleware
    app.add_middleware(ObservabilityMiddleware)

    # 2. Initialize state components
    mgr = session_manager or SessionManager()
    gw = gateway or ModelGateway()
    # Pass gw.primary_model so AgentLoop and ModelGateway stay aligned in telemetry
    loop = agent_loop or AgentLoop(model=gw.primary_model, gateway=gw)

    # Ensure gateway is synchronized with the selected model identifier
    if not gw.primary_model:
        gw.primary_model = loop.model

    app.state.session_manager = mgr
    app.state.gateway = gw
    app.state.agent_loop = loop

    # ========================================================================
    # OBSERVABILITY & HEALTH ENDPOINTS
    # ========================================================================

    @app.get(
        "/healthz",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Liveness Probe",
    )
    async def health_check() -> HealthResponse:
        """Returns 200 OK with service version and UTC timestamp."""
        return HealthResponse()

    @app.get(
        "/readyz",
        tags=["Health"],
        summary="Readiness Probe",
    )
    async def ready_check(
        manager: SessionManager = Depends(get_session_manager),
    ) -> dict[str, Any]:
        """
        Readiness probe verifying SQLite connectivity and model provider configuration.
        """
        # 1. Verify SQLite sandbox creation
        try:
            test_conn = SandboxDB.create_connection()
            test_conn.close()
            db_status = "ready"
        except Exception as exc:
            logger.error("Readiness probe failed database check: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database sandbox check failed: {exc}",
            )

        # 2. Verify provider configuration
        cfg = get_provider_config()

        return {
            "status": "ready",
            "provider": cfg.provider,
            "model": cfg.model_identifier,
            "database": db_status,
            "active_sessions": manager.active_session_count(),
        }

    @app.get(
        "/metrics",
        tags=["Observability"],
        summary="Prometheus Metrics",
        include_in_schema=False,
    )
    async def prometheus_metrics() -> Response:
        """Exports Prometheus scrape metrics."""
        payload, content_type = get_metrics_payload()
        return Response(content=payload, media_type=content_type)

    # ========================================================================
    # AGENT EXECUTION ENDPOINTS
    # ========================================================================

    @app.post(
        "/v1/agent/run",
        response_model=AgentRunResponse,
        status_code=status.HTTP_200_OK,
        tags=["Agent"],
        summary="Run Customer Support Agent",
    )
    async def run_agent(
        request: Request,
        payload: AgentRunRequest,
        manager: SessionManager = Depends(get_session_manager),
        loop: AgentLoop = Depends(get_agent_loop),
    ) -> AgentRunResponse:
        """
        Executes a multi-turn agent interaction.
        1. Retrieves or creates an isolated SQLite sandbox for payload.session_id.
        2. Executes the AgentLoop with tool calling, trace correlation, and policy enforcement.
        3. Records agent runtime, token, and tool metrics to Prometheus.
        4. Returns the agent's textual response and operational trajectory telemetry.
        """
        try:
            # 1. Resolve or initialize sandbox context for session
            session = manager.get_or_create(
                session_id=payload.session_id,
                customer_id=payload.customer_id,
            )
            # 2. Execute agent loop with correlation request ID
            req_id = getattr(request.state, "request_id", None)
            trajectory = loop.run(
                user_prompt=payload.prompt,
                session=session,
                task_id=payload.task_id,
                request_id=req_id,
            )

            # Count assistant reasoning turns
            step_count = len([e for e in trajectory.events if e.event_type == "MODEL_RESPONSE"])
            exit_reason_str = str(
                trajectory.exit_reason.value
                if hasattr(trajectory.exit_reason, "value")
                else trajectory.exit_reason
            )

            # 3. Record Agent-level Prometheus Telemetry
            model_name = loop.model
            AGENT_RUNS_TOTAL.labels(model=model_name, exit_reason=exit_reason_str).inc()
            AGENT_RUN_DURATION_SECONDS.labels(model=model_name).observe(trajectory.usage.latency_ms / 1000.0)

            AGENT_TOKENS_TOTAL.labels(model=model_name, token_type="prompt").inc(trajectory.usage.prompt_tokens)
            AGENT_TOKENS_TOTAL.labels(model=model_name, token_type="completion").inc(trajectory.usage.completion_tokens)

            # Record domain tool call metrics from trajectory events
            for event in trajectory.events:
                if event.event_type == "TOOL_RESULT":
                    t_name = "unknown_tool"
                    if event.content and event.content.startswith("Tool "):
                        parts = event.content.split()
                        if len(parts) >= 2:
                            t_name = parts[1]
                    t_result = event.tool_result or {}
                    t_status = "success" if t_result.get("success", False) else "error"
                    AGENT_TOOL_CALLS_TOTAL.labels(tool_name=t_name, status=t_status).inc()

            # 4. Format response
            return AgentRunResponse(
                session_id=payload.session_id,
                response=trajectory.final_response,
                exit_reason=exit_reason_str,
                step_count=step_count,
                tokens=TokenUsageSchema(
                    prompt_tokens=trajectory.usage.prompt_tokens,
                    completion_tokens=trajectory.usage.completion_tokens,
                    total_tokens=trajectory.usage.total_tokens,
                ),
                latency_ms=round(trajectory.usage.latency_ms, 2),
                model=model_name,
                prompt_version="v1.0",
            )
        except Exception as exc:
            logger.exception("Error executing agent run for session %s: %s", payload.session_id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent execution encountered an unrecoverable error: {exc}",
            )

    @app.delete(
        "/v1/agent/sessions/{session_id}",
        tags=["Agent"],
        summary="Terminate Session",
    )
    async def terminate_session(
        session_id: str,
        manager: SessionManager = Depends(get_session_manager),
    ) -> dict[str, Any]:
        """Explicitly terminates a session and closes its SQLite sandbox."""
        closed = manager.close_session(session_id)
        if not closed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found or already terminated.",
            )
        return {"status": "terminated", "session_id": session_id}

    return app


# Default ASGI application instance for uvicorn
app = create_app()
