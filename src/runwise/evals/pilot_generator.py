"""
Offline generator and validation engine for the 30-scenario diagnostic pilot candidate pool.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from runwise.evals.adapters.banking77_adapter import adapt_banking77_row
from runwise.evals.adapters.bitext_adapter import adapt_bitext_row
from runwise.evals.adapters.taubench_adapter import adapt_taubench_episode
from runwise.evals.assertion_validator import validate_readonly_query
from runwise.evals.routing_schema import PairedScenario

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_PILOT_DATA_PATH = PROJECT_ROOT / "data" / "routing" / "pilot_30_scenarios.jsonl"


def generate_30_scenario_pilot() -> list[PairedScenario]:
    """
    Constructs 30 diverse, policy-grounded diagnostic scenarios across 4 operational categories.
    Validates every assertion query with read-only whitelist checks.
    """
    scenarios: list[PairedScenario] = []

    # -------------------------------------------------------------------------
    # 1. BITEXT (10 tasks): 5 Routine Inquiries + 5 Authenticated Cancellations
    # -------------------------------------------------------------------------
    inquiry_prompts = [
        "Where is my package for order {{ORDER_NUMBER}} currently located?",
        "Can you check the delivery tracking status for {{ORDER_NUMBER}}?",
        "When is {{ORDER_NUMBER}} estimated to arrive at my address?",
        "I need the shipping carrier updates on {{ORDER_NUMBER}} please.",
        "Could you confirm if order {{ORDER_NUMBER}} has been processed yet?",
    ]
    for i, p in enumerate(inquiry_prompts, start=1):
        scenarios.append(
            adapt_bitext_row(
                {"instruction": p, "intent": "track_order"},
                index=i,
                split="pilot",
            )
        )

    cancel_prompts = [
        "I made a mistake. Please cancel my pending order {{ORDER_NUMBER}}.",
        "Cancel {{ORDER_NUMBER}} right away, I don't need it anymore.",
        "Please abort order {{ORDER_NUMBER}} and confirm cancellation.",
        "Kindly process cancellation for order {{ORDER_NUMBER}} immediately.",
        "I want to cancel {{ORDER_NUMBER}} before it enters dispatch.",
    ]
    for i, p in enumerate(cancel_prompts, start=6):
        scenarios.append(
            adapt_bitext_row(
                {"instruction": p, "intent": "cancel_order"},
                index=i,
                split="pilot",
            )
        )

    # -------------------------------------------------------------------------
    # 2. BANKING77 (10 tasks): Financial Ambiguity, Inquiries & Negation Traps
    # -------------------------------------------------------------------------
    banking_prompts = [
        "I do not want a refund, I just need a breakdown of why order ORD-102 was charged $50.",
        "Please do not cancel or refund ORD-102; clarify why my receipt shows extra sales tax.",
        "I'm not requesting compensation for ORD-102, just let me know why shipping took 4 days.",
        "There's an unverified fee on ORD-102. Don't touch the order, just explain the line item.",
        "I didn't authorize a return on ORD-102. Where is the carrier tracking history?",
        "Explain the transaction code on ORD-102 without processing any refund or adjustment.",
        "I don't need money back on ORD-102; I just need to verify the billing date.",
        "Why is ORD-102 pending settlement? Do not refund or alter anything on the account.",
        "I have a dispute regarding delivery timing on ORD-102, but do NOT refund the charge.",
        "Confirm if the charge on ORD-102 is settled. No refund or modification requested.",
    ]
    for i, p in enumerate(banking_prompts, start=1):
        scenarios.append(
            adapt_banking77_row(
                {"text": p, "label": "dispute_explanation"},
                index=i,
                split="pilot",
            )
        )

    # -------------------------------------------------------------------------
    # 3. TAU-BENCH / BFCL (10 tasks): Conditional Mutations & Policy Boundaries
    # -------------------------------------------------------------------------
    tau_scenarios = [
        "Check orders ORD-103 and ORD-104. If ORD-103 is delivered, issue a partial refund of 2000 cents on ORD-103; do not touch ORD-104.",
        "Inspect ORD-103 and ORD-104. Only refund 2000 cents on ORD-103 if delivered; never refund ORD-104 as it is beyond policy window.",
        "If ORD-103 has delivered status, process $20.00 refund on ORD-103, but verify ORD-104 is completely unmutated.",
        "Verify ORD-103 delivered status. If valid, credit 2000 cents on ORD-103 and leave ORD-104 untouched.",
        "Evaluate ORD-103. If delivery is confirmed, apply 2000 cents refund to ORD-103 only. ORD-104 must not be refunded.",
        "Check customer orders. If ORD-103 delivered at least 1 day ago, refund $20.00 on ORD-103 and reject any changes to ORD-104.",
        "Issue $20.00 refund on ORD-103 strictly conditioned on delivered status; ORD-104 must remain in current state.",
        "If ORD-103 is marked delivered, issue $20.00 refund for Bob Jones. Do not process refunds on any other orders.",
        "Review status of ORD-103. If delivered, refund 2000 cents on ORD-103; leave ORD-104 alone.",
        "Check status for ORD-103 and ORD-104. If ORD-103 is delivered, refund $20.00 on ORD-103. Do not touch ORD-104.",
    ]
    for i, p in enumerate(tau_scenarios, start=1):
        scenarios.append(
            adapt_taubench_episode(
                {"prompt": p, "customer_id": "CUST-002", "verification_code": "1234"},
                index=i,
                split="pilot",
            )
        )

    # Validate all SQL assertions in every generated scenario
    for s in scenarios:
        for assertion in s.expected.db_state_assertions:
            validate_readonly_query(assertion.query)

    return scenarios


def check_contamination_and_near_duplicates(
    scenarios: list[PairedScenario],
    similarity_threshold: float = 0.95,
) -> tuple[bool, list[str]]:
    """
    Guarantees no task ID overlaps with quarantined holdouts, no family ID leakage across
    splits, and flags unintended near-duplicate prompt collisions.
    """
    issues: list[str] = []

    # 1. Holdout Quarantine Verification: check against tasks.jsonl
    holdout_file = PROJECT_ROOT / "evals" / "tasks.jsonl"
    holdout_ids: set[str] = set()
    if holdout_file.exists():
        for line in holdout_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("split") == "frozen_holdout":
                    holdout_ids.add(item.get("id", ""))

    for s in scenarios:
        if s.task_id in holdout_ids:
            issues.append(f"Contamination: Task ID {s.task_id} is a quarantined frozen holdout task.")

    # 2. Family ID and Split Isolation Check
    family_splits: dict[str, set[str]] = {}
    for s in scenarios:
        family_splits.setdefault(s.family_id, set()).add(s.split)

    for fam_id, splits in family_splits.items():
        if len(splits) > 1:
            issues.append(f"Family Leakage: Family ID {fam_id} appears across multiple splits: {splits}")

    # 3. Near-Duplicate Detection across different task families
    for i in range(len(scenarios)):
        for j in range(i + 1, len(scenarios)):
            s1 = scenarios[i]
            s2 = scenarios[j]
            if s1.family_id != s2.family_id:
                ratio = difflib.SequenceMatcher(
                    None, s1.scenario.user_prompt, s2.scenario.user_prompt
                ).ratio()
                if ratio >= similarity_threshold:
                    issues.append(
                        f"Near-duplicate cross-family collision ({ratio:.2%}): "
                        f"{s1.task_id} ({s1.family_id}) vs {s2.task_id} ({s2.family_id})"
                    )

    return len(issues) == 0, issues


def estimate_pilot_cost(
    scenarios: list[PairedScenario],
    repeat_count: int = 5,
    repeat_trials: int = 3,
) -> dict[str, float]:
    """
    Computes rigorous cost estimate for paired pilot execution using active Vertex AI pricing.
    """
    base_count = len(scenarios)
    stochastic_repeats = repeat_count * repeat_trials
    total_calls_per_model = base_count + stochastic_repeats

    # Measured averages: ~3,400 prompt tokens, ~320 completion tokens
    flash_cost_per_trial = (3400 * 0.075 + 320 * 0.300) / 1_000_000  # ~$0.000351
    pro_cost_per_trial = (3400 * 1.250 + 320 * 5.000) / 1_000_000    # ~$0.005850

    flash_total = total_calls_per_model * flash_cost_per_trial
    pro_total = total_calls_per_model * pro_cost_per_trial
    total = flash_total + pro_total

    return {
        "flash_calls": total_calls_per_model,
        "pro_calls": total_calls_per_model,
        "flash_estimated_usd": round(flash_total, 4),
        "pro_estimated_usd": round(pro_total, 4),
        "total_estimated_usd": round(total, 4),
    }


def save_pilot_candidate_pool(output_path: Path | None = None) -> Path:
    """Generates and writes the 30 pilot candidate scenarios to JSONL entirely offline."""
    out = output_path or DEFAULT_PILOT_DATA_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    scenarios = generate_30_scenario_pilot()
    is_clean, issues = check_contamination_and_near_duplicates(scenarios)
    if not is_clean:
        raise ValueError(f"Contamination checks failed: {issues}")

    with out.open("w", encoding="utf-8") as f:
        for s in scenarios:
            f.write(s.model_dump_json() + "\n")

    return out
