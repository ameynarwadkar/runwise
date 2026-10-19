"""
Pydantic data models for paired routing evaluations, task provenance, and ground truth assertions.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

from runwise.evals.models import DBAssertion, Task, TaskExpected


class ProvenanceRecord(BaseModel):
    """Source provenance tracking for public or authored datasets."""
    source_dataset: str
    source_row_id: str
    upstream_license: str
    original_text: str
    adaptation_strategy: str
    attribution_type: Literal[
        "imported_source_row",
        "authored_inspired_by_benchmark",
        "authored_internal_policy",
    ] = "authored_internal_policy"
    is_authored_template: bool = False


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
    auth_before_mutation: bool = True
    expected_tool_order: list[str] = Field(default_factory=list)
    allowed_tool_paths: list[list[str]] = Field(default_factory=list)
    factual_patterns: list[str] = Field(default_factory=list)
    explanation_patterns: list[str] = Field(default_factory=list)
    refusal_patterns: list[str] = Field(default_factory=list)
    grounded_response_keywords: list[str] = Field(default_factory=list)


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

    def to_eval_task(self) -> Task:
        """Translates PairedScenario into a native Runwise Task for standard tiered grading."""
        db_assertions = [
            DBAssertion(
                query=a.query,
                expected_value=a.expected_value,
                operator=a.operator,
                rationale=a.rationale,
            )
            for a in self.expected.db_state_assertions
        ]
        return Task(
            id=self.task_id,
            split=self.split,
            category=self.category,
            difficulty=self.difficulty,
            user_prompt=self.scenario.user_prompt,
            customer_id=self.scenario.customer_id,
            injected_clock_iso=self.scenario.injected_clock_iso,
            expected=TaskExpected(
                db_state_assertions=db_assertions,
                required_tools=self.expected.required_tools,
                forbidden_tools=self.expected.forbidden_tools,
                must_authenticate=self.expected.must_authenticate,
                expected_refusal=self.expected.expected_refusal,
                requires_judge=False,
                expected_tool_order=self.expected.expected_tool_order,
                allowed_tool_paths=self.expected.allowed_tool_paths,
                factual_patterns=self.expected.factual_patterns,
                explanation_patterns=self.expected.explanation_patterns,
                refusal_patterns=self.expected.refusal_patterns,
                grounded_response_keywords=self.expected.grounded_response_keywords,
                auth_before_mutation=self.expected.auth_before_mutation,
            ),
        )
