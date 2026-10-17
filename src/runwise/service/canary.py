"""
Dynamic Canary Traffic Router & Variant Configuration Engine.

Implements session-consistent weighted traffic splitting according to llmops.md:
- Stable vs Canary model and prompt version management.
- Cryptographically uniform, deterministic session hashing to prevent mid-session prompt flips.
- Zero-rebuild dynamic config updates and JSON file persistence for one-command rollbacks.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import threading
from typing import Any
from pydantic import BaseModel, Field, field_validator


class CanaryConfig(BaseModel):
    """Configuration for canary traffic routing and rollback thresholds."""
    enabled: bool = False
    weight: float = Field(default=0.0, ge=0.0, le=1.0)
    stable_model: str = "vertex_ai/gemini-2.5-flash"
    stable_prompt_version: str = "v1.0"
    canary_model: str = "vertex_ai/gemini-2.5-pro"
    canary_prompt_version: str = "v2.0"
    rollback_p95_latency_threshold_ms: float = 3000.0
    rollback_error_rate_threshold: float = 0.05

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Canary weight must be between 0.0 and 1.0")
        return v


class RouteDecision(BaseModel):
    """Telemetry and routing decision returned for an incoming request."""
    variant: str               # "stable" or "canary"
    model: str                 # LiteLLM model string
    prompt_version: str        # e.g. "v1.0" or "v2.0"
    is_canary: bool
    weight: float
    routing_key: str | None = None


class CanaryRouter:
    """
    Thread-safe dynamic traffic router supporting runtime hot-reloads and rollbacks.
    """

    def __init__(self, config: CanaryConfig | None = None):
        self._config = config or self._load_initial_config()
        self._lock = threading.RLock()

    @classmethod
    def _load_initial_config(cls) -> CanaryConfig:
        """Loads configuration from environment variables or defaults."""
        enabled = os.getenv("CANARY_ENABLED", "false").lower() in ("true", "1", "yes")
        try:
            weight = float(os.getenv("CANARY_WEIGHT", "0.0"))
        except ValueError:
            weight = 0.0

        return CanaryConfig(
            enabled=enabled,
            weight=weight,
            stable_model=os.getenv("STABLE_MODEL", "vertex_ai/gemini-2.5-flash"),
            stable_prompt_version=os.getenv("STABLE_PROMPT_VERSION", "v1.0"),
            canary_model=os.getenv("CANARY_MODEL", "vertex_ai/gemini-2.5-pro"),
            canary_prompt_version=os.getenv("CANARY_PROMPT_VERSION", "v2.0"),
        )

    @property
    def config(self) -> CanaryConfig:
        with self._lock:
            return self._config.model_copy()

    def update_config(self, **kwargs: Any) -> CanaryConfig:
        """Thread-safely updates configuration in-place."""
        with self._lock:
            updated_dict = self._config.model_dump()
            updated_dict.update(kwargs)
            self._config = CanaryConfig(**updated_dict)
            return self._config.model_copy()

    def load_from_file(self, config_path: Path | str) -> CanaryConfig:
        """Loads configuration atomically from a JSON file."""
        path = Path(config_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with self._lock:
            self._config = CanaryConfig(**data)
            return self._config.model_copy()

    def save_to_file(self, config_path: Path | str) -> None:
        """Persists current configuration to a JSON file."""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = self._config.model_dump()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def route(
        self,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> RouteDecision:
        """
        Routes a request to 'stable' or 'canary' using session-consistent hashing.
        """
        with self._lock:
            cfg = self._config

        # Short-circuit if canary is disabled or weight is zero
        if not cfg.enabled or cfg.weight <= 0.0:
            return RouteDecision(
                variant="stable",
                model=cfg.stable_model,
                prompt_version=cfg.stable_prompt_version,
                is_canary=False,
                weight=cfg.weight,
                routing_key=session_id or request_id,
            )

        # Short-circuit if weight is 100%
        if cfg.weight >= 1.0:
            return RouteDecision(
                variant="canary",
                model=cfg.canary_model,
                prompt_version=cfg.canary_prompt_version,
                is_canary=True,
                weight=cfg.weight,
                routing_key=session_id or request_id,
            )

        # Consistent cryptographic hashing on session_id or request_id
        routing_key = session_id or request_id
        if routing_key:
            # Hash to deterministic float [0.0, 1.0)
            digest = hashlib.sha256(f"canary_salt:{routing_key}".encode("utf-8")).digest()
            int_val = int.from_bytes(digest[:4], "big")
            hash_ratio = int_val / 0xFFFFFFFF
            is_canary = hash_ratio < cfg.weight
        else:
            # Fallback to random uniform distribution
            is_canary = random.random() < cfg.weight

        if is_canary:
            return RouteDecision(
                variant="canary",
                model=cfg.canary_model,
                prompt_version=cfg.canary_prompt_version,
                is_canary=True,
                weight=cfg.weight,
                routing_key=routing_key,
            )
        else:
            return RouteDecision(
                variant="stable",
                model=cfg.stable_model,
                prompt_version=cfg.stable_prompt_version,
                is_canary=False,
                weight=cfg.weight,
                routing_key=routing_key,
            )


# Global default router instance for the service lifecycle
_DEFAULT_ROUTER: CanaryRouter | None = None
_ROUTER_LOCK = threading.Lock()


def get_canary_router() -> CanaryRouter:
    """Dependency provider for FastAPI returning the singleton CanaryRouter."""
    global _DEFAULT_ROUTER
    if _DEFAULT_ROUTER is None:
        with _ROUTER_LOCK:
            if _DEFAULT_ROUTER is None:
                _DEFAULT_ROUTER = CanaryRouter()
    return _DEFAULT_ROUTER


def reset_canary_router() -> None:
    """Reset the singleton instance (used in tests)."""
    global _DEFAULT_ROUTER
    with _ROUTER_LOCK:
        _DEFAULT_ROUTER = None
