"""
Adapter for galileo-ai/agent-leaderboard and tau-bench customer service episodes.
License: Apache 2.0 (Galileo) / MIT (Sierra tau-bench)
"""

from __future__ import annotations

from typing import Any

from runwise.evals.assertion_validator import build_structured_assertion
from runwise.evals.routing_schema import (
    ExpectedBehavior,
    PairedScenario,
    ProvenanceRecord,
    ScenarioPayload,
)


def adapt_taubench_episode(
    episode: dict[str, Any],
    index: int,
    split: str = "pilot",
    family_suffix: str = "",
) -> PairedScenario:
    raw_prompt = episode.get("prompt", "")
    cid = episode.get("customer_id", "CUST-002")
    code = episode.get("verification_code", "1234")

    prompt = f"{raw_prompt} Customer ID: {cid}, code: {code}."
    fam_tag = family_suffix or f"{index:03d}"
    family_id = f"fam_tau_cond_{fam_tag}"

    # Verifies conditional refund on ORD-103 occurred while ORD-104 is completely unmutated
    assertions = [
        build_structured_assertion(
            table="refunds",
            column="amount_cents",
            filter_column="order_id",
            filter_value="ORD-103",
            expected_value=2000,
            aggregate="SUM_COALESCE",
            rationale="ORD-103 delivered balance refund of 2000 cents must be recorded",
        ),
        build_structured_assertion(
            table="refunds",
            column="*",
            filter_column="order_id",
            filter_value="ORD-104",
            expected_value=0,
            aggregate="COUNT",
            rationale="ORD-104 must not be refunded due to condition or policy exclusion",
        ),
    ]

    return PairedScenario(
        task_id=f"rw_tau_{index:04d}",
        family_id=family_id,
        provenance=ProvenanceRecord(
            source_dataset="galileo-ai/agent-leaderboard",
            source_row_id=f"episode_{index}",
            upstream_license="Apache-2.0 / MIT",
            original_text=raw_prompt,
            adaptation_strategy="conditional_mutation_asserted",
            attribution_type="authored_inspired_by_benchmark",
            is_authored_template=True,
        ),
        split=split,
        category="conditional_mutation",
        difficulty="hard",
        scenario=ScenarioPayload(
            user_prompt=prompt,
            customer_id=cid,
        ),
        expected=ExpectedBehavior(
            db_state_assertions=assertions,
            required_tools=["lookup_order", "verify_customer", "issue_refund"],
            forbidden_tools=[],
            must_authenticate=True,
            expected_refusal=False,
        ),
    )
