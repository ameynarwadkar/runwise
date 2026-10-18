"""
Integration tests for Runwise Public Playground & Demo Endpoints:
- GET /v1/demo/scenarios
- POST /v1/demo/scenarios/run
- Sanitization of timeline events and tool calls
- Unregistered conversational queries marked as NOT_EVALUATED
"""

import pytest
from fastapi.testclient import TestClient

from runwise.service.app import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_list_canonical_scenarios(client):
    """Verifies that GET /v1/demo/scenarios returns the 5 pre-seeded canonical scenarios."""
    response = client.get("/v1/demo/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert isinstance(scenarios, list)
    assert len(scenarios) == 5

    scenario_ids = [s["id"] for s in scenarios]
    assert "scenario_order_lookup" in scenario_ids
    assert "scenario_address_update" in scenario_ids
    assert "scenario_refund_request" in scenario_ids
    assert "scenario_multi_order_dispute" in scenario_ids
    assert "scenario_adversarial_injection" in scenario_ids

    # Validate essential fields for frontend rendering
    for s in scenarios:
        assert "id" in s
        assert "task_id" in s
        assert "title" in s
        assert "expected_tier" in s
        assert "prompt" in s
        assert "expected_route_reason" in s


def test_run_scenario_not_found(client):
    """Verifies that an unknown scenario ID returns a clean 404."""
    response = client.post("/v1/demo/scenarios/run", json={"scenario_id": "scenario_invalid_xyz"})
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_run_scenario_order_lookup(client):
    """
    Executes scenario_order_lookup against isolated sandbox database.
    Verifies AutoRouter picks Flash, timeline events are sanitized,
    and deterministic evaluation is executed.
    """
    payload = {
        "scenario_id": "scenario_order_lookup",
        "auto_route": True,
    }
    response = client.post("/v1/demo/scenarios/run", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Model and Routing verification
    assert "gemini-2.5-flash" in data["model"]
    assert data["complexity_score"] is not None
    assert data["complexity_score"] < 0.45
    assert data["is_replay"] is False

    # Cost calculation verification
    assert data["cost_usd"] is not None
    assert data["cost_usd"] >= 0.0

    # Sanitized timeline events verification
    assert "events" in data
    assert len(data["events"]) >= 3
    event_types = [e["event_type"] for e in data["events"]]
    assert "REQUEST_RECEIVED" in event_types
    assert "ROUTING_DECISION" in event_types
    assert "FINAL_RESPONSE" in event_types

    # Ensure no internal prompts or raw traces leaked
    for event in data["events"]:
        assert "system_prompt" not in event["summary"].lower()
        assert "internal" not in event["summary"].lower()

    # Deterministic evaluation verification
    assert "evaluation" in data
    assert data["evaluation"] is not None
    assert data["evaluation"]["overall_status"] in ["PASS", "FAIL"]
    assert "explanation" in data["evaluation"]


def test_run_scenario_adversarial_routes_to_pro(client):
    """
    Executes scenario_adversarial_injection.
    Verifies AutoRouter detects adversarial regex, assigns high complexity,
    routes to Gemini 2.5 Pro, and evaluates policy compliance.
    """
    payload = {
        "scenario_id": "scenario_adversarial_injection",
        "auto_route": True,
    }
    response = client.post("/v1/demo/scenarios/run", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "gemini-2.5-pro" in data["model"]
    assert data["complexity_score"] is not None
    assert data["complexity_score"] >= 0.45
    assert any("adversarial" in f.lower() for f in data.get("features_detected", [])) or "threshold" in data["routing_reason"].lower()


def test_conversation_mode_never_labels_unverified_as_pass(client):
    """
    Verifies rule: Never label unverified conversational queries as a verified PASS.
    Custom conversational queries must return NOT_EVALUATED.
    """
    payload = {
        "prompt": "Hello! Can you help me check if an order exists?",
        "session_id": "test_conv_unverified_1",
        "auto_route": True,
    }
    response = client.post("/v1/agent/run", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "evaluation" in data
    assert data["evaluation"] is not None
    assert data["evaluation"]["overall_status"] == "NOT_EVALUATED"
    assert "not registered" in data["evaluation"]["explanation"].lower() or "ad-hoc" in data["evaluation"]["explanation"].lower()
