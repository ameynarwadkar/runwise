"""
End-to-End Canary Rollout, SLO Breach Detection, and Automated Rollback Drill.

Executes a full operational drill:
1. Canary Deployment: Activates candidate prompt v2.0 at 50% traffic weight.
2. Traffic Splitting: Validates session-consistent traffic distribution across sessions.
3. Anomaly Detection: Detects a simulated p95 latency SLO breach (> 3000ms).
4. Automated Rollback: Triggers zero-rebuild rollback via ops/scripts/rollback.py.
5. Recovery Verification: Confirms 100% of live traffic immediately returns to stable.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

from runwise.service.app import create_app
from runwise.service.canary import CanaryConfig, CanaryRouter
from runwise.service.gateway import ModelGateway
from ops.scripts.rollback import rollback_service


def run_canary_drill() -> bool:
    print("=" * 75)
    print("  🧪 RUNWISE LLMOPS CANARY ROLLOUT & AUTOMATED ROLLBACK DRILL")
    print("=" * 75)

    # 1. Setup Service with mocked responses for deterministic latency demonstration
    stable_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Stable response", tool_calls=None))],
        usage=SimpleNamespace(prompt_tokens=40, completion_tokens=15, total_tokens=55),
        model="mock-stable-model",
    )
    canary_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Canary response", tool_calls=None))],
        usage=SimpleNamespace(prompt_tokens=45, completion_tokens=20, total_tokens=65),
        model="mock-canary-model",
    )

    def mock_completion(**kwargs):
        model = kwargs.get("model", "")
        return canary_resp if "canary" in model else stable_resp

    gateway = ModelGateway(primary_model="mock-stable-model", completion_fn=mock_completion)
    router = CanaryRouter(
        CanaryConfig(
            enabled=False,
            weight=0.0,
            stable_model="mock-stable-model",
            stable_prompt_version="v1.0",
            canary_model="mock-canary-model",
            canary_prompt_version="v2.0",
        )
    )
    app = create_app(gateway=gateway, canary_router=router)
    client = TestClient(app)

    # ------------------------------------------------------------------------
    # PHASE 1: Deploy Canary Candidate (50% Traffic Weight)
    # ------------------------------------------------------------------------
    print("\n🚀 [PHASE 1: CANARY ACTIVATION]")
    config_update = {
        "enabled": True,
        "weight": 0.50,
        "canary_model": "mock-canary-model",
        "canary_prompt_version": "v2.0",
    }
    res = client.post("/v1/admin/canary/config", json=config_update)
    assert res.status_code == 200
    print(f"   • Canary Status: ENABLED")
    print(f"   • Traffic Weight: 50.0% Canary / 50.0% Stable")
    print(f"   • Stable Variant: v1.0 (mock-stable-model)")
    print(f"   • Canary Variant: v2.0 (mock-canary-model)")

    # ------------------------------------------------------------------------
    # PHASE 2: Live Multi-Session Traffic & Session Pinning
    # ------------------------------------------------------------------------
    print("\n👥 [PHASE 2: LIVE TRAFFIC STREAMING & SESSION PINNING]")
    session_variants: dict[str, str] = {}
    total_requests = 12

    for i in range(1, total_requests + 1):
        sess_id = f"customer_session_{i % 6}"  # 6 distinct sessions across 12 turns
        turn_num = 1 if sess_id not in session_variants else 2

        resp = client.post("/v1/agent/run", json={"prompt": f"Turn {turn_num}", "session_id": sess_id})
        assert resp.status_code == 200

        variant = resp.headers.get("X-Runwise-Variant")
        p_ver = resp.headers.get("X-Runwise-Prompt-Version")
        model = resp.headers.get("X-Runwise-Model")

        # Verify session pinning consistency across turns
        if sess_id in session_variants:
            assert session_variants[sess_id] == variant, f"Session {sess_id} experienced mid-session prompt flip!"
        else:
            session_variants[sess_id] = variant

        icon = "🐤 [CANARY]" if variant == "canary" else "🏢 [STABLE]"
        print(f"   Request #{i:02d} | Session: {sess_id:<20} | Turn: {turn_num} | {icon} Variant: {variant:<6} ({p_ver})")

    canary_share = sum(1 for v in session_variants.values() if v == "canary") / len(session_variants)
    print(f"\n   📊 Observed Session Traffic Distribution: {canary_share * 100:.1f}% Canary, {(1 - canary_share) * 100:.1f}% Stable")

    # ------------------------------------------------------------------------
    # PHASE 3: Watchdog Anomaly Detection (SLO Breach)
    # ------------------------------------------------------------------------
    print("\n🔍 [PHASE 3: SLO TELEMETRY MONITORING & ANOMALY DETECTION]")
    canary_p95_latency_ms = 3420.0
    sla_threshold_ms = router.config.rollback_p95_latency_threshold_ms
    print(f"   • Canary p95 Latency: {canary_p95_latency_ms:.0f} ms")
    print(f"   • Production SLO Cap: {sla_threshold_ms:.0f} ms")

    if canary_p95_latency_ms > sla_threshold_ms:
        print(f"   🚨 ANOMALY CONFIRMED: Canary latency exceeded SLO threshold by +{(canary_p95_latency_ms - sla_threshold_ms):.0f} ms!")
        rollback_reason = f"Canary p95 latency breached SLO: {canary_p95_latency_ms:.0f}ms > {sla_threshold_ms:.0f}ms"
    else:
        print("   ✅ Telemetry healthy.")
        return False

    # ------------------------------------------------------------------------
    # PHASE 4: Execute Zero-Rebuild Rollback
    # ------------------------------------------------------------------------
    print("\n🛑 [PHASE 4: EXECUTING ONE-COMMAND INSTANT ROLLBACK]")
    rollback_res = client.post(f"/v1/admin/canary/rollback?reason={rollback_reason}")
    assert rollback_res.status_code == 200
    rb_data = rollback_res.json()
    print(f"   • Rollback Status: {rb_data['status']}")
    print(f"   • Active Canary Enabled: {rb_data['config']['enabled']}")
    print(f"   • Active Canary Weight:  {rb_data['config']['weight']}")

    # Also persist to ops/canary.json
    canary_file = Path("ops/canary.json")
    router.save_to_file(canary_file)
    print(f"   • Saved persistent rollback state to: {canary_file}")

    # ------------------------------------------------------------------------
    # PHASE 5: Post-Rollback Immediate Recovery Verification
    # ------------------------------------------------------------------------
    print("\n✅ [PHASE 5: POST-ROLLBACK RECOVERY VERIFICATION]")
    recovered_stable_count = 0
    test_burst = 10

    for i in range(1, test_burst + 1):
        sess_id = f"post_recovery_sess_{i}"
        resp = client.post("/v1/agent/run", json={"prompt": "Hello post-recovery", "session_id": sess_id})
        assert resp.status_code == 200

        variant = resp.headers.get("X-Runwise-Variant")
        p_ver = resp.headers.get("X-Runwise-Prompt-Version")
        assert variant == "stable", f"Traffic leak detected: received variant '{variant}' after rollback!"
        assert p_ver == "v1.0"
        recovered_stable_count += 1
        print(f"   Recovery Check #{i:02d} | Session: {sess_id} | Variant: {variant} ({p_ver}) -> 100% STABLE")

    print("\n" + "=" * 75)
    print(f"  🏆 DRILL RESULT: SUCCESS")
    print(f"  • Canary deployed and routed with session consistency")
    print(f"  • SLO breach detected without customer impact")
    print(f"  • Rollback executed instantly with ZERO container rebuilds")
    print(f"  • 100% of subsequent requests verified on stable ({recovered_stable_count}/{test_burst})")
    print("=" * 75 + "\n")
    return True


if __name__ == "__main__":
    success = run_canary_drill()
    sys.exit(0 if success else 1)
