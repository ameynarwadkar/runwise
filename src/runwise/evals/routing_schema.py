"""
Pydantic data models for paired routing evaluations, task provenance, and ground truth assertions.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ProvenanceRecord(BaseModel):
    """Source provenance tracking for adapted datasets."""
    source_dataset: str
    source_row_id: str
    original_text: str
    adaptation_strategy: str


class AssertionQuery(BaseModel):
    """Declarative read-only assertion query against ephemeral SQLite sandbox."""
    query: str
    expected_value: Any
    operator: Literal["equals", "greater_than", "less_than", "contains"] = "equals"
    rationale: str = ""


class ExpectedBehavior(BaseModel):
    """Expected agent actions and verified database state."""
    db_state_assertions: list[AssertionQuery] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    must_authenticate: bool = False
    expected_refusal: bool = False


class ScenarioPayload(BaseModel):
    """Concrete scenario input given to the agent."""
    user_prompt: str
    customer_id: str | None = None
    injected_clock_iso: str = "2026-10-15T12:00:00Z"


class TrialOutcomeRecord(BaseModel):
    """Measured performance metrics for an evaluation trial."""
    trials_attempted: int = 0
    trials_passed: int = 0
    passed: bool | None = None
    tier_failures: list[str] = Field(default_factory=list)
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None


class PairedEvaluationOutcome(BaseModel):
    """Paired Flash vs Pro evaluation record."""
    status: Literal["pending", "completed", "invalid_eval", "provider_error"] = "pending"
    flash: TrialOutcomeRecord = Field(default_factory=TrialOutcomeRecord)
    pro: TrialOutcomeRecord = Field(default_factory=TrialOutcomeRecord)
    outcome_category: Literal[
        "PASS_PASS", "FAIL_PASS", "PASS_FAIL", "FAIL_FAIL", "UNDETERMINED"
    ] = "UNDETERMINED"
    escalation_benefit: bool = False
    eval_valid: bool = True


class PairedScenario(BaseModel):
    """Complete paired routing scenario record with isolated family_id."""
    task_id: str
    family_id: str
    provenance: ProvenanceRecord
    split: Literal["train", "val", "test", "pilot"]
    category: str
    difficulty: Literal["easy", "medium", "hard"]
    scenario: ScenarioPayload
    expected: ExpectedBehavior
    paired_eval: PairedEvaluationOutcome = Field(default_factory=PairedEvaluationOutcome)
