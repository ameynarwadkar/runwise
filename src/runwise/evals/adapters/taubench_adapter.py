"""
Adapter for galileo-ai/agent-leaderboard and tau-bench customer service episodes.
License: Apache 2.0 (Galileo) / MIT (Sierra tau-bench)
"""

from __future__ import annotations

from typing import Any

from runwise.evals.routing_schema import (
    AssertionQuery,
    ExpectedBehavior,
    PairedScenario,
    ProvenanceRecord,
    ScenarioPayload,
)


def adapt_taubench_episode(episode: dict[str, Any], index: int, split: str = "pilot") -> PairedScenario:
    raw_prompt = episode.get("prompt", "")
    cid = episode.get("customer_id", "CUST-002")
    code = episode.get("verification_code", "1234")

    prompt = f"{raw_prompt} Customer ID: {cid}, code: {code}."
    family_id = f"fam_tau_cond_{index // 5:03d}"

    # Verifies that conditional refund on ORD-103 occurs while ORD-104 remains untouched
    assertions = [
        AssertionQuery(
            query="SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = 'ORD-103'",
            expected_value=2000,
            operator="equals",
            rationale="ORD-103 eligible balance refund of 2000 cents must be recorded",
        ),
        AssertionQuery(
            query="SELECT COUNT(*) FROM refunds WHERE order_id = 'ORD-104'",
            expected_value=0,
            operator="equals",
            rationale="ORD-104 must not be refunded due to condition or policy exclusion",
        ),
    ]

    return PairedScenario(
        task_id=f"rw_tau_{index:04d}",
        family_id=family_id,
        provenance=ProvenanceRecord(
            source_dataset="galileo-ai/agent-leaderboard",
            source_row_id=f"episode_{index}",
            original_text=raw_prompt,
            adaptation_strategy="conditional_mutation_asserted",
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
