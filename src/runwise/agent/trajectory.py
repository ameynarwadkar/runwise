"""
Data structures for capturing immutable trial execution trajectories.

Every trial produces a complete trajectory record with deterministic sequence
numbers, conversation state, tool calls, token usage, and granular exit reasons.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ExitReason(str, Enum):
    """Granular reasons for agent loop termination."""
    NORMAL_COMPLETION = "NORMAL_COMPLETION"      # Model terminated without tool calls
    MAX_STEPS_EXCEEDED = "MAX_STEPS_EXCEEDED"    # Reached iteration limit
    PROVIDER_ERROR = "PROVIDER_ERROR"            # Unrecoverable API/network error
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"# Unparseable response
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"      # Wall-clock timeout exceeded
    CANCELLED = "CANCELLED"                      # Aborted by harness


class TrajectoryEvent(BaseModel):
    """An individual sequenced event within a trial."""
    seq: int                                     # Deterministic sequence number (1, 2, 3...)
    event_type: str                              # USER_INPUT, MODEL_RESPONSE, TOOL_RESULT
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_result: dict[str, Any] | None = None
    timestamp_iso: str | None = None


class TokenUsage(BaseModel):
    """Resource consumption metrics for a trial."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    latency_ms: float = 0.0


class Trajectory(BaseModel):
    """The complete immutable execution record of a trial."""
    task_id: str
    trial_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    events: list[TrajectoryEvent] = Field(default_factory=list)
    exit_reason: ExitReason = ExitReason.NORMAL_COMPLETION
    usage: TokenUsage = Field(default_factory=TokenUsage)
    final_response: str = ""

    def add_event(
        self,
        event_type: str,
        content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_result: dict[str, Any] | None = None,
    ) -> None:
        """Appends a new event with the next deterministic sequence number."""
        next_seq = len(self.events) + 1
        self.events.append(
            TrajectoryEvent(
                seq=next_seq,
                event_type=event_type,
                content=content,
                tool_calls=tool_calls,
                tool_result=tool_result,
            )
        )
