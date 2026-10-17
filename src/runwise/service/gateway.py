"""
Model Gateway and Reliability Layer for the Runwise HTTP Service.

Wraps model completion calls with:
- Per-call timeouts.
- Exponential backoff with jitter on transient failures (429, 5xx, timeouts).
- Fail-fast behavior on client errors (400, 401, 403).
- Automatic fallback to a secondary model if the primary model fails.
- In-memory metrics and Prometheus counters tracking retry and fallback events.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Callable

import litellm

from runwise.service.metrics import GATEWAY_FALLBACKS_TOTAL, GATEWAY_RETRIES_TOTAL

logger = logging.getLogger(__name__)

# Standard retryable HTTP status codes
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class GatewayStats:
    """Operational telemetry counters recorded by the gateway."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retry_count: int = 0
    fallback_count: int = 0


def is_retryable_error(exc: Exception) -> bool:
    """
    Determines if an exception represents a transient failure eligible for retry.
    """
    if isinstance(
        exc,
        (
            litellm.RateLimitError,
            litellm.InternalServerError,
            litellm.ServiceUnavailableError,
            litellm.Timeout,
            litellm.APIConnectionError,
            TimeoutError,
        ),
    ):
        return True

    # Check for status_code attribute on HTTP exceptions
    status_code = getattr(exc, "status_code", None)
    if status_code in RETRYABLE_STATUS_CODES:
        return True

    # Never retry client bad requests or auth errors
    if isinstance(exc, (litellm.BadRequestError, litellm.AuthenticationError, litellm.NotFoundError)):
        return False

    msg = str(exc).lower()
    return any(term in msg for term in ["429", "rate limit", "quota exceeded", "timeout", "timed out", "503", "502"])


class ModelGateway:
    """
    Resilient gateway providing timeouts, retries, and fallback over LiteLLM.
    """

    def __init__(
        self,
        primary_model: str | None = None,
        fallback_model: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 5.0,
        completion_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.completion_fn = completion_fn or litellm.completion
        self.stats = GatewayStats()

    def complete(
        self,
        model: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Executes a completion call with timeout, retries, and fallback.

        Attempts primary model first. If retries are exhausted and a fallback_model
        is configured, attempts the fallback model before raising an exception.
        """
        self.stats.total_requests += 1
        target_primary = model or self.primary_model
        if not target_primary:
            raise ValueError("No model specified for completion.")

        call_messages = messages or []

        try:
            # 1. Attempt with primary model
            response = self._execute_with_retries(
                model=target_primary,
                messages=call_messages,
                tools=tools,
                temperature=temperature,
                api_key=api_key,
                **kwargs,
            )
            self.stats.successful_requests += 1
            return response
        except Exception as primary_exc:
            logger.warning(
                "Primary model %s failed after %d retries: %s",
                target_primary,
                self.max_retries,
                primary_exc,
            )

            # 2. Check if fallback model is configured and different from primary
            if self.fallback_model and self.fallback_model != target_primary:
                logger.info("Engaging gateway fallback to secondary model: %s", self.fallback_model)
                self.stats.fallback_count += 1
                try:
                    GATEWAY_FALLBACKS_TOTAL.labels(
                        primary_model=target_primary,
                        fallback_model=self.fallback_model,
                    ).inc()
                except Exception:
                    pass

                try:
                    response = self._execute_with_retries(
                        model=self.fallback_model,
                        messages=call_messages,
                        tools=tools,
                        temperature=temperature,
                        api_key=api_key,
                        **kwargs,
                    )
                    self.stats.successful_requests += 1
                    return response
                except Exception as fallback_exc:
                    logger.error("Fallback model %s also failed: %s", self.fallback_model, fallback_exc)
                    self.stats.failed_requests += 1
                    raise fallback_exc

            self.stats.failed_requests += 1
            raise primary_exc

    def _execute_with_retries(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Executes a single model target with exponential backoff and jitter."""
        attempt = 0
        while True:
            try:
                call_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "timeout": self.timeout_seconds,
                    **kwargs,
                }
                if tools is not None:
                    call_kwargs["tools"] = tools
                if api_key:
                    call_kwargs["api_key"] = api_key

                return self.completion_fn(**call_kwargs)

            except Exception as exc:
                attempt += 1
                if attempt > self.max_retries or not is_retryable_error(exc):
                    raise exc

                self.stats.retry_count += 1
                try:
                    reason = "transient_error"
                    err_str = str(exc).lower()
                    if "429" in err_str or "rate limit" in err_str or isinstance(exc, getattr(litellm, "RateLimitError", ())):
                        reason = "rate_limit_429"
                    elif "timeout" in err_str or isinstance(exc, (getattr(litellm, "Timeout", ()), TimeoutError)):
                        reason = "timeout"
                    elif any(c in err_str for c in ["500", "502", "503", "504"]):
                        reason = "server_error_5xx"
                    GATEWAY_RETRIES_TOTAL.labels(model=model, reason=reason).inc()
                except Exception:
                    pass

                # Calculate backoff delay with jitter
                delay = min(
                    self.max_delay_seconds,
                    self.base_delay_seconds * (2 ** (attempt - 1)),
                )
                jitter = random.uniform(0.0, 0.1 * delay)
                total_delay = delay + jitter

                logger.warning(
                    "Retryable error on attempt %d/%d for model %s (%s). Retrying in %.2fs...",
                    attempt,
                    self.max_retries,
                    model,
                    exc,
                    total_delay,
                )
                time.sleep(total_delay)
