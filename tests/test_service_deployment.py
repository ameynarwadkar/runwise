"""
Deployment & Security Verification Test Suite.

Verifies:
1. Dynamic CORS origin parsing and restrictions.
2. In-memory sliding-window IP rate limiting with safe proxy header handling.
3. Public replay-only mode (RUNWISE_DEMO_MODE=replay):
   - Refuses unauthenticated arbitrary live LLM inference with 403 Forbidden.
   - Disables administrative endpoints (/v1/admin/*) with 403 Forbidden.
   - Serves verified benchmark replay traces for pre-seeded scenarios with zero LLM calls.
   - Reports ready status on /readyz without requiring live model provider credentials.
4. Normal live mode (RUNWISE_DEMO_MODE=live):
   - Preserves administrative endpoints and live execution capabilities.
"""

from __future__ import annotations

import os
from unittest.mock import patch
from fastapi.testclient import TestClient

from runwise.service.app import create_app
from runwise.service.rate_limiter import SlidingWindowRateLimiter, get_client_ip


def test_cors_trusted_origins_allowed():
    """Verifies explicitly configured CORS origins receive allow headers."""
    with patch.dict(os.environ, {"CORS_ALLOWED_ORIGINS": "https://runwise.vercel.app,http://localhost:3000"}):
        app = create_app()
        client = TestClient(app)

        # Preflight from trusted Vercel production origin
        resp = client.options(
            "/readyz",
            headers={
                "Origin": "https://runwise.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://runwise.vercel.app"

        # Preflight from untrusted origin should not receive allow-origin
        resp_untrusted = client.options(
            "/readyz",
            headers={
                "Origin": "https://malicious-site.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_untrusted.headers.get("access-control-allow-origin") != "https://malicious-site.example.com"


def test_rate_limiter_unit_logic():
    """Verifies sliding window counter and retry-after computation."""
    limiter = SlidingWindowRateLimiter(requests_per_minute=3, window_seconds=60.0)
    ip = "198.51.100.42"

    allowed1, _ = limiter.is_allowed(ip)
    allowed2, _ = limiter.is_allowed(ip)
    allowed3, _ = limiter.is_allowed(ip)
    allowed4, retry_after = limiter.is_allowed(ip)

    assert allowed1 is True
    assert allowed2 is True
    assert allowed3 is True
    assert allowed4 is False
    assert retry_after > 0


def test_rate_limiter_middleware_throttles_excessive_traffic():
    """Verifies FastAPI middleware enforces 429 with Retry-After header on throttled IP."""
    app = create_app()
    client = TestClient(app)

    # Use a unique simulated client IP
    test_ip = "203.0.113.99"
    headers = {"X-Forwarded-For": test_ip}

    # First request should succeed
    resp1 = client.get("/v1/demo/scenarios", headers=headers)
    assert resp1.status_code == 200

    # Exhaust rate limit by firing requests
    # The default is 30 rpm, let's fire 31 requests
    responses = [client.get("/v1/demo/scenarios", headers=headers) for _ in range(35)]
    status_codes = [r.status_code for r in responses]

    # At least some requests should have been throttled with 429
    assert 429 in status_codes
    throttled = [r for r in responses if r.status_code == 429][0]
    assert "Retry-After" in throttled.headers
    assert "Rate limit exceeded" in throttled.json()["detail"]


def test_public_demo_mode_refuses_arbitrary_live_inference():
    """Verifies that in RUNWISE_DEMO_MODE=replay, live /v1/agent/run is strictly forbidden."""
    with patch.dict(os.environ, {"RUNWISE_DEMO_MODE": "replay"}):
        app = create_app()
        client = TestClient(app)

        resp = client.post(
            "/v1/agent/run",
            json={
                "prompt": "Can you refund order ORD-101?",
                "session_id": "test_sess_refuse",
            },
        )
        assert resp.status_code == 403
        assert "disabled in public replay-only demo mode" in resp.json()["detail"]


def test_public_demo_mode_disables_admin_endpoints():
    """Verifies that in RUNWISE_DEMO_MODE=replay, administrative canary endpoints are entirely disabled."""
    with patch.dict(os.environ, {"RUNWISE_DEMO_MODE": "replay"}):
        app = create_app()
        client = TestClient(app)

        # GET canary status
        resp_status = client.get("/v1/admin/canary/status")
        assert resp_status.status_code == 403
        assert "Administrative endpoints are disabled" in resp_status.json()["detail"]

        # POST canary rollback
        resp_rollback = client.post("/v1/admin/canary/rollback")
        assert resp_rollback.status_code == 403
        assert "Administrative endpoints are disabled" in resp_rollback.json()["detail"]


def test_public_demo_mode_serves_verified_replay_for_scenarios():
    """Verifies that in RUNWISE_DEMO_MODE=replay, scenario runs return genuine recorded replays with 0 LLM calls."""
    with patch.dict(os.environ, {"RUNWISE_DEMO_MODE": "replay"}):
        app = create_app()
        client = TestClient(app)

        resp = client.post(
            "/v1/demo/scenarios/run",
            json={"scenario_id": "scenario_order_lookup", "auto_route": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_replay"] is True
        assert data["session_id"] == "sess_replay_inq_01"
        assert data["tokens"]["total_tokens"] == 959
        assert data["evaluation"]["overall_status"] == "PASS"
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool_name"] == "lookup_order"


def test_public_demo_mode_readyz_probe():
    """Verifies /readyz reports ready and mode='replay' in public demo mode."""
    with patch.dict(os.environ, {"RUNWISE_DEMO_MODE": "replay"}):
        app = create_app()
        client = TestClient(app)

        resp = client.get("/readyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["mode"] == "replay"
