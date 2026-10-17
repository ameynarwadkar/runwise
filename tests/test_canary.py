"""
Unit Tests for Canary Router and Dynamic Traffic Splitting.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from runwise.service.canary import CanaryConfig, CanaryRouter


def test_disabled_canary_always_routes_stable():
    router = CanaryRouter(CanaryConfig(enabled=False, weight=0.5))
    for i in range(50):
        decision = router.route(session_id=f"sess_{i}")
        assert decision.variant == "stable"
        assert decision.is_canary is False
        assert decision.prompt_version == "v1.0"


def test_zero_weight_always_routes_stable():
    router = CanaryRouter(CanaryConfig(enabled=True, weight=0.0))
    for i in range(50):
        decision = router.route(session_id=f"sess_{i}")
        assert decision.variant == "stable"
        assert decision.is_canary is False


def test_full_weight_always_routes_canary():
    router = CanaryRouter(CanaryConfig(enabled=True, weight=1.0))
    for i in range(50):
        decision = router.route(session_id=f"sess_{i}")
        assert decision.variant == "canary"
        assert decision.is_canary is True
        assert decision.prompt_version == "v2.0"


def test_session_consistent_hashing():
    """Verify that a given session always hits the exact same variant across turns."""
    router = CanaryRouter(CanaryConfig(enabled=True, weight=0.30))
    
    # Check 100 sessions over 10 consecutive turns each
    for s_idx in range(100):
        sess_id = f"session_customer_{s_idx}"
        first_decision = router.route(session_id=sess_id)
        for _ in range(10):
            subsequent_decision = router.route(session_id=sess_id)
            assert subsequent_decision.variant == first_decision.variant
            assert subsequent_decision.model == first_decision.model
            assert subsequent_decision.prompt_version == first_decision.prompt_version


def test_traffic_distribution_statistical_validity():
    """Verify traffic splits close to target weight across large population."""
    weight = 0.25
    router = CanaryRouter(CanaryConfig(enabled=True, weight=weight))
    
    total = 2000
    canary_count = sum(
        1 for i in range(total) if router.route(session_id=f"user_session_{i}").is_canary
    )
    observed_ratio = canary_count / total
    # Expected: 25% ± 3.5%
    assert 0.215 <= observed_ratio <= 0.285


def test_dynamic_in_memory_rollback():
    """Verify in-memory hot update immediately reverts all traffic to stable."""
    router = CanaryRouter(CanaryConfig(enabled=True, weight=0.50))
    
    # Trigger rollback
    router.update_config(enabled=False, weight=0.0)
    assert router.config.enabled is False
    assert router.config.weight == 0.0

    for i in range(50):
        decision = router.route(session_id=f"sess_{i}")
        assert decision.variant == "stable"
        assert decision.is_canary is False


def test_file_persistence_and_reload(tmp_path: Path):
    """Verify config can be saved to and loaded from ops/canary.json."""
    config_file = tmp_path / "canary.json"
    initial_config = CanaryConfig(
        enabled=True,
        weight=0.15,
        canary_model="vertex_ai/gemini-2.5-pro",
        canary_prompt_version="v2.1",
    )
    router = CanaryRouter(initial_config)
    router.save_to_file(config_file)
    assert config_file.exists()

    # Load into a new router instance
    fresh_router = CanaryRouter()
    loaded_config = fresh_router.load_from_file(config_file)
    assert loaded_config.enabled is True
    assert loaded_config.weight == 0.15
    assert loaded_config.canary_prompt_version == "v2.1"
