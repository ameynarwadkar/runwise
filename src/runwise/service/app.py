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
from fastapi.middleware.cors import CORSMiddleware

from runwise.agent.loop import AgentLoop
from runwise.config import get_provider_config
from runwise.domain.db import SandboxDB
from runwise.service.gateway import ModelGateway
from runwise.service.canary import CanaryRouter, get_canary_router
from runwise.service.cost import calculate_cost_breakdown
from runwise.service.demo import build_sanitized_timeline, demo_router
from runwise.service.metrics import (
    ACTIVE_SESSIONS,
    AGENT_RUN_DURATION_SECONDS,
    AGENT_RUNS_TOTAL,
    AGENT_TOKENS_TOTAL,
    AGENT_TOOL_CALLS_TOTAL,
    CANARY_LATENCY_SECONDS,
    CANARY_REQUESTS_TOTAL,
    ROUTER_DECISIONS_TOTAL,
    get_metrics_payload,
)
from runwise.service.middleware import ObservabilityMiddleware
from runwise.service.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    EvaluationSummarySchema,
    GraderStatusEnum,
    HealthResponse,
    TokenUsageSchema,
)
from runwise.service.session import SessionManager
from runwise.service.auto_router import AutoRouter, AutoRouterConfig

logger = logging.getLogger(__name__)

_auto_router_instance: AutoRouter | None = None

def get_auto_router() -> AutoRouter:
    global _auto_router_instance
    if _auto_router_instance is None:
        _auto_router_instance = AutoRouter(AutoRouterConfig())
    return _auto_router_instance

def get_session_manager(request: Request) -> SessionManager:
    """FastAPI dependency resolving the active SessionManager instance."""
    return request.app.state.session_manager


def get_agent_loop(request: Request) -> AgentLoop:
    """FastAPI dependency resolving the active AgentLoop instance."""
    return request.app.state.agent_loop

def get_canary_router_dep(request: Request) -> CanaryRouter:
    """FastAPI dependency resolving the active CanaryRouter instance."""
    return getattr(request.app.state, "canary_router", None) or get_canary_router()


def create_app(
    session_manager: SessionManager | None = None,
    gateway: ModelGateway | None = None,
    agent_loop: AgentLoop | None = None,
    canary_router: CanaryRouter | None = None,
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

    # 2. Configure CORS for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Mount Public Demo & Scenario Endpoints
    app.include_router(demo_router)

    # 4. Initialize state components
    mgr = session_manager or SessionManager()
    gw = gateway or ModelGateway()
    # Pass gw.primary_model so AgentLoop and ModelGateway stay aligned in telemetry
    loop = agent_loop or AgentLoop(model=gw.primary_model, gateway=gw)
    
    cr = canary_router or get_canary_router()
    # Ensure gateway is synchronized with the selected model identifier
    if not gw.primary_model:
        gw.primary_model = loop.model

    app.state.session_manager = mgr
    app.state.gateway = gw
    app.state.agent_loop = loop
    app.state.canary_router = cr
    app.state.auto_router = get_auto_router()
    
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
        response: Response,
        payload: AgentRunRequest,
        manager: SessionManager = Depends(get_session_manager),
        loop: AgentLoop = Depends(get_agent_loop),
        router: CanaryRouter = Depends(get_canary_router_dep),
        auto_router: AutoRouter = Depends(get_auto_router),
    ) -> AgentRunResponse:
        """
        Executes a multi-turn agent interaction.
        1. Retrieves or creates an isolated SQLite sandbox for payload.session_id.
        2. Executes the AgentLoop with tool calling, trace correlation, and policy enforcement.
        3. Records agent runtime, token, and tool metrics to Prometheus.
        4. Returns the agent's textual response and operational trajectory telemetry.
        """
        try:
            # 1. Resolve canary/variant routing decision via session-consistent hashing
            req_id = getattr(request.state, "request_id", None)
            decision = router.route(session_id=payload.session_id, request_id=req_id)

            # 2. Resolve target model: AutoRouter -> Canary Rollout -> Default Loop/Gateway Model
            complexity_score = None
            routing_reason = None

            if payload.auto_route:
                route_dec = auto_router.route(payload.prompt)
                target_model = route_dec.selected_model
                complexity_score = route_dec.complexity_score
                routing_reason = route_dec.decision_reason

                risk_tier = "high" if route_dec.complexity_score >= auto_router.config.complexity_threshold else "low"
                ROUTER_DECISIONS_TOTAL.labels(selected_model=target_model, risk_tier=risk_tier).inc()

                response.headers["X-Runwise-Complexity-Score"] = str(complexity_score)
                response.headers["X-Runwise-Routed-Model"] = target_model
            elif decision.is_canary:
                target_model = decision.model
            else:
                target_model = loop.model

            # Propagate transparent observability headers
            response.headers["X-Runwise-Variant"] = decision.variant
            response.headers["X-Runwise-Prompt-Version"] = decision.prompt_version
            response.headers["X-Runwise-Model"] = target_model

            # 3. Resolve or initialize sandbox context for session
            session = manager.get_or_create(
                session_id=payload.session_id,
                customer_id=payload.customer_id,
            )

            # 4. Instantiate loop if target model or prompt version differs from default loop
            active_loop = loop
            target_prompt_version = decision.prompt_version
            if loop.model != target_model or loop.prompt_version != target_prompt_version:
                active_loop = AgentLoop(
                    model=target_model,
                    prompt_version=target_prompt_version,
                    gateway=loop.gateway,
                )

            trajectory = active_loop.run(
                user_prompt=payload.prompt,
                session=session,
                task_id=payload.task_id,
                request_id=req_id,
            )
            step_count = len([e for e in trajectory.events if e.event_type == "MODEL_RESPONSE"])
            exit_reason_str = str(
                trajectory.exit_reason.value
                if hasattr(trajectory.exit_reason, "value")
                else trajectory.exit_reason
            )
            # 4. Record Agent-level and Canary-level Prometheus Telemetry
            model_name = active_loop.model
            AGENT_RUNS_TOTAL.labels(model=model_name, exit_reason=exit_reason_str).inc()
            AGENT_RUN_DURATION_SECONDS.labels(model=model_name).observe(trajectory.usage.latency_ms / 1000.0)
            AGENT_TOKENS_TOTAL.labels(model=model_name, token_type="prompt").inc(trajectory.usage.prompt_tokens)
            AGENT_TOKENS_TOTAL.labels(model=model_name, token_type="completion").inc(trajectory.usage.completion_tokens)
            CANARY_REQUESTS_TOTAL.labels(
                variant=decision.variant,
                model=model_name,
                prompt_version=decision.prompt_version,
                status="success",
            ).inc()
            CANARY_LATENCY_SECONDS.labels(
                variant=decision.variant,
                model=model_name,
            ).observe(trajectory.usage.latency_ms / 1000.0)
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
            # 5. Calculate cost, format sanitized timeline and tool calls
            cost_breakdown = calculate_cost_breakdown(
                model=model_name,
                prompt_tokens=trajectory.usage.prompt_tokens,
                completion_tokens=trajectory.usage.completion_tokens,
            )
            eval_summary = EvaluationSummarySchema(
                overall_status=GraderStatusEnum.NOT_EVALUATED,
                explanation="Ad-hoc conversational turn without registered ground truth assertions.",
            )
            events, tool_calls = build_sanitized_timeline(
                trajectory=trajectory,
                complexity_score=complexity_score,
                routing_reason=routing_reason,
                model_name=model_name,
                evaluation=eval_summary,
            )

            # 6. Format response
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
                latency_ms=trajectory.usage.latency_ms,
                model=model_name,
                prompt_version=decision.prompt_version,
                variant=decision.variant,
                complexity_score=complexity_score,
                routing_reason=routing_reason,
                features_detected=features_detected if 'features_detected' in locals() else [],
                cost_usd=cost_breakdown.total_cost_usd,
                is_replay=False,
                tool_calls=tool_calls,
                events=events,
                evaluation=eval_summary,
            )
        except Exception as exc:
            logger.exception("Error executing agent run for session %s: %s", payload.session_id, exc)
            model_for_metrics = "unknown_model"
            if 'decision' in locals():
                model_for_metrics = decision.model if decision.model else "unknown_model"
            elif 'loop' in locals():
                model_for_metrics = loop.model if loop.model else "unknown_model"
            
            AGENT_RUNS_TOTAL.labels(model=model_for_metrics, exit_reason="error").inc()
            if 'decision' in locals() and decision.is_canary:
                CANARY_REQUESTS_TOTAL.labels(
                    variant=decision.variant,
                    model=model_for_metrics,
                    prompt_version=decision.prompt_version,
                    status="error",
                ).inc()
            
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

        # ========================================================================
    # CANARY & TRAFFIC MANAGEMENT ENDPOINTS
    # ========================================================================

    @app.get(
        "/v1/admin/canary/status",
        tags=["Admin"],
        summary="Get Canary Configuration",
    )
    async def get_canary_status(
        router: CanaryRouter = Depends(get_canary_router_dep),
    ) -> dict[str, Any]:
        """Returns the active runtime canary traffic routing configuration."""
        return router.config.model_dump()

    @app.post(
        "/v1/admin/canary/config",
        tags=["Admin"],
        summary="Update Canary Configuration",
    )
    async def update_canary_config(
        payload: dict[str, Any],
        router: CanaryRouter = Depends(get_canary_router_dep),
    ) -> dict[str, Any]:
        """Dynamically updates canary configuration at runtime without rebuild."""
        updated = router.update_config(**payload)
        return {"status": "updated", "config": updated.model_dump()}

    @app.post(
        "/v1/admin/canary/rollback",
        tags=["Admin"],
        summary="Roll Back Canary Immediately",
    )
    async def trigger_canary_rollback(
        reason: str = "Manual or automated rollback triggered",
        router: CanaryRouter = Depends(get_canary_router_dep),
    ) -> dict[str, Any]:
        """Immediately disables canary traffic and resets weight to 0.0."""
        updated = router.update_config(enabled=False, weight=0.0)
        logger.warning("Canary rollback executed. Reason: %s", reason)
        return {
            "status": "rolled_back",
            "reason": reason,
            "config": updated.model_dump(),
        }

    return app


# Default ASGI application instance for uvicorn
app = create_app()
