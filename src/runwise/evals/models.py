"""
Data contracts for evaluation tasks, assertions, and grader outcomes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class GraderStatus(str, Enum):
    """Standard outcome status for an individual grader."""
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # For optional task criteria
    ERROR = "ERROR"                    # Harness or execution failure; never blamed on the agent


class TrialOutcome(str, Enum):
    """Overall outcome for a trial across all combined graders."""
    PASS = "PASS"
    FAIL = "FAIL"
    EVAL_ERROR = "EVAL_ERROR"          # One or more required graders encountered an ERROR


class GraderResult(BaseModel):
    """Structured report emitted by every grader tier."""
    grader_name: str
    status: GraderStatus
    reason_code: str                   # e.g., 'STATE_MATCH', 'ASSERTION_FAILED', 'UNAUTHORIZED_MUTATION'
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class DBAssertion(BaseModel):
    """A single verifiable SQL assertion evaluated against the post-trial database."""
    query: str
    expected_value: Any
    operator: str = "equals"           # 'equals', 'greater_than', 'less_than', 'is_null', 'not_null'
    rationale: str = ""


class TaskExpected(BaseModel):
    """Expected outcomes and constraints for a task."""
    db_state_assertions: list[DBAssertion] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    must_authenticate: bool = False
    expected_refusal: bool = False
    requires_judge: bool = False


class Task(BaseModel):
    """Specification of an evaluation scenario from tasks.jsonl."""
    id: str
    split: str                         # 'dev' or 'frozen_holdout'
    category: str                      # 'cancellation', 'refund', 'address_update', 'adversarial', etc.
    difficulty: str                    # 'easy', 'medium', 'hard'
    user_prompt: str
    customer_id: str | None = None
    injected_clock_iso: str = "2026-10-15T12:00:00Z"
    expected: TaskExpected = Field(default_factory=TaskExpected)
