"""
In-Memory Sliding-Window Rate Limiting Engine.

Architectural Limitations of this In-Memory Implementation:
------------------------------------------------------------
1. Ephemeral State: Rate limit counters reside in-process memory and reset
   whenever the server process restarts or spins down (e.g. Render Free Tier
   15-minute idle sleep).
2. Per-Worker Isolation: In multi-worker Uvicorn configurations, counters
   are maintained per worker process rather than globally across workers.
3. Cluster Scalability: For horizontally-scaled deployments across multiple
   instances or containers, a centralized distributed store (e.g., Redis or
   Upstash) is required.
4. Single-Instance Suitability: For single-container deployments on Render or
   Cloud Run, this provides effective, zero-dependency abuse deterrence
   without infrastructure cost.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """
    Safely resolves the client IP behind reverse proxies (Render, Vercel, Cloudflare).

    Security note on proxy headers:
    Standard reverse proxies append the client IP to X-Forwarded-For.
    We take the first non-empty IP in the chain (the originating client),
    or fall back to the direct socket connection host.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        parts = [ip.strip() for ip in xff.split(",") if ip.strip()]
        if parts:
            return parts[0]

    # Check X-Real-IP
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()

    # Fallback to direct client socket
    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


class SlidingWindowRateLimiter:
    """Sliding-window request rate limiter indexed by client IP."""

    def __init__(self, requests_per_minute: int = 30, window_seconds: float = 60.0):
        self.rpm = requests_per_minute
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> Tuple[bool, int]:
        """
        Determines if a request from client_ip is allowed under the rate limit.

        Returns:
            (allowed: bool, retry_after_seconds: int)
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Prune expired timestamps
        timestamps = [t for t in self._hits[client_ip] if t > cutoff]
        self._hits[client_ip] = timestamps

        if len(timestamps) >= self.rpm:
            oldest = timestamps[0]
            retry_after = max(1, int(oldest + self.window_seconds - now))
            return False, retry_after

        self._hits[client_ip].append(now)
        return True, 0

    def reset(self) -> None:
        """Clears all stored rate limit records (useful for testing)."""
        self._hits.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware applying sliding-window rate limiting to public execution endpoints.
    Health checks, readiness probes, and metrics endpoints are exempt.
    """

    def __init__(self, app, requests_per_minute: int = 30):
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter(requests_per_minute=requests_per_minute)
        # Endpoints exempt from rate limiting
        self.exempt_paths = {"/healthz", "/readyz", "/metrics", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip rate limit for exempt utility routes or pre-flight OPTIONS
        if path in self.exempt_paths or request.method == "OPTIONS":
            return await call_next(request)

        # Rate limit only customer/demo endpoints
        if path.startswith("/v1/"):
            client_ip = get_client_ip(request)
            allowed, retry_after = self.limiter.is_allowed(client_ip)

            if not allowed:
                logger.warning("Rate limit exceeded for IP: %s on %s", client_ip, path)
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Rate limit exceeded ({self.limiter.rpm} requests/minute). Please slow down."
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)
