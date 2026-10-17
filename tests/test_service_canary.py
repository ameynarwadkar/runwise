"""
Integration tests for Canary Traffic Routing and Response Headers in FastAPI Service.
"""

from types import SimpleNamespace
from fastapi.testclient import TestClient
import pytest

from runwise.service.app import create_app
from runwise.service.canary import CanaryConfig, CanaryRouter
from runwise.service.gateway import ModelGateway


def _make_mock_response(content: str = "Test response") -> SimpleNamespace:
    msg = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(prompt_tokens=25, completion_tokens=10, total_tokens=35)
    return SimpleNamespace(choices=[choice], usage=usage, model="mock-model")


def test_default_routing_emits_stable_headers():
    mock_resp = _make_mock_response("Hello from stable")
    gateway = ModelGateway(primary_model="mock-stable", completion_fn=lambda **kw: mock_resp)
    app = create_app(gateway=gateway, canary_router=CanaryRouter(CanaryConfig(enabled=False)))
    client = TestClient(app)

    res = client.post("/v1/agent/run", json={"prompt": "Hi", "session_id": "sess_default"})
    assert res.status_code == 200
    assert res.headers["X-Runwise-Variant"] == "stable"
    assert res.headers["X-Runwise-Prompt-Version"] == "v1.0"
    data = res.json()
    assert data["variant"] == "stable"
    assert data["prompt_version"] == "v1.0"


def test_full_canary_routing_emits_canary_headers():
    mock_resp = _make_mock_response("Hello from canary")
    gateway = ModelGateway(primary_model="mock-canary", completion_fn=lambda **kw: mock_resp)
    canary_cfg = CanaryConfig(
        enabled=True,
        weight=1.0,
        canary_model="mock-canary",
        canary_prompt_version="v2.0",
    )
    app = create_app(gateway=gateway, canary_router=CanaryRouter(canary_cfg))
    client = TestClient(app)

    res = client.post("/v1/agent/run", json={"prompt": "Hi", "session_id": "sess_canary"})
    assert res.status_code == 200
    assert res.headers["X-Runwise-Variant"] == "canary"
    assert res.headers["X-Runwise-Prompt-Version"] == "v2.0"
    data = res.json()
    assert data["variant"] == "canary"
    assert data["prompt_version"] == "v2.0"


def test_session_consistent_routing_across_multi_turns():
    """Verify Turn 1 and Turn 2 for the same session receive identical variant headers."""
    mock_resp = _make_mock_response("Consistent response")
    gateway = ModelGateway(primary_model="mock-gateway", completion_fn=lambda **kw: mock_resp)
    router = CanaryRouter(CanaryConfig(enabled=True, weight=0.50))
    app = create_app(gateway=gateway, canary_router=router)
    client = TestClient(app)

    sess_id = "sess_pinned_001"
    turn1 = client.post("/v1/agent/run", json={"prompt": "Turn 1", "session_id": sess_id})
    turn2 = client.post("/v1/agent/run", json={"prompt": "Turn 2", "session_id": sess_id})

    assert turn1.status_code == 200
    assert turn2.status_code == 200
    assert turn1.headers["X-Runwise-Variant"] == turn2.headers["X-Runwise-Variant"]
    assert turn1.headers["X-Runwise-Prompt-Version"] == turn2.headers["X-Runwise-Prompt-Version"]


def test_dynamic_in_memory_rollback_takes_effect_immediately():
    """Verify toggling enabled=False immediately reverts subsequent requests to stable."""
    mock_resp = _make_mock_response("Rollback response")
    gateway = ModelGateway(primary_model="mock-model", completion_fn=lambda **kw: mock_resp)
    router = CanaryRouter(CanaryConfig(enabled=True, weight=1.0, canary_prompt_version="v2.0"))
    app = create_app(gateway=gateway, canary_router=router)
    client = TestClient(app)

    # Initial request -> canary
    res1 = client.post("/v1/agent/run", json={"prompt": "Hi", "session_id": "sess_rollback"})
    assert res1.headers["X-Runwise-Variant"] == "canary"

    # Trigger hot rollback
    router.update_config(enabled=False, weight=0.0)

    # Immediate next request -> stable
    res2 = client.post("/v1/agent/run", json={"prompt": "Hi", "session_id": "sess_rollback"})
    assert res2.headers["X-Runwise-Variant"] == "stable"
    assert res2.headers["X-Runwise-Prompt-Version"] == "v1.0"
def test_admin_canary_status_and_update():
    """Verify GET and POST /v1/admin/canary endpoints."""
    router = CanaryRouter(CanaryConfig(enabled=False, weight=0.0))
    app = create_app(canary_router=router)
    client = TestClient(app)

    # 1. Check initial status
    status_res = client.get("/v1/admin/canary/status")
    assert status_res.status_code == 200
    assert status_res.json()["enabled"] is False

    # 2. Update configuration
    update_res = client.post("/v1/admin/canary/config", json={"enabled": True, "weight": 0.20})
    assert update_res.status_code == 200
    assert update_res.json()["config"]["enabled"] is True
    assert update_res.json()["config"]["weight"] == 0.20

    # 3. Verify status reflects update
    status_res2 = client.get("/v1/admin/canary/status")
    assert status_res2.json()["weight"] == 0.20


def test_admin_canary_rollback_endpoint():
    """Verify POST /v1/admin/canary/rollback immediately zeroes out canary weight."""
    router = CanaryRouter(CanaryConfig(enabled=True, weight=0.75))
    app = create_app(canary_router=router)
    client = TestClient(app)

    rollback_res = client.post("/v1/admin/canary/rollback?reason=Latency_Spike")
    assert rollback_res.status_code == 200
    data = rollback_res.json()
    assert data["status"] == "rolled_back"
    assert data["config"]["enabled"] is False
    assert data["config"]["weight"] == 0.0

    # Confirmed on router
    assert router.config.enabled is False
    assert router.config.weight == 0.0
