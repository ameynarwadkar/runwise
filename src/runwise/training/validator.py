"""
Strict dataset validation, security invariant enforcement, and contamination detection for SFT.

Validates:
1. Pydantic schema conformance and turn integrity.
2. Tool call syntax and schema adherence against TOOL_SCHEMAS.
3. Authentication and authorization sequencing (strict ordering: verify_customer first, no parallel mutations).
4. Anti-fabrication (tool responses must conform strictly to ToolResult schemas, no orphaned IDs).
5. Impossible policy transitions (no cancelling shipped/delivered orders, no refunds past 30 days).
6. Credential leakage prevention (no assistant leakage of tokens, keys, passwords, or customer PINs).
7. Comprehensive contamination guards:
   - Entity ID quarantine (CUST-001..CUST-005, CUST-999, ORD-101..ORD-105, ORD-777, ORD-888, ORD-999).
   - SequenceMatcher lexical similarity against frozen holdout.
   - Scenario template slot-normalized matching.
   - Paraphrase and n-gram overlap detection.
   - Reserved task-family collision detection.
   - Expected tool trajectory clone detection.
"""

from __future__ import annotations

import difflib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runwise.agent.dispatcher import TOOL_SCHEMAS
from runwise.training.schemas import SFTExample

PROTECTED_MUTATIONS = {"cancel_order", "update_shipping_address", "issue_refund"}

QUARANTINED_ENTITIES = {
    "CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005", "CUST-999",
    "ORD-101", "ORD-102", "ORD-103", "ORD-104", "ORD-105", "ORD-777", "ORD-888", "ORD-999",
}

RESERVED_TASK_FAMILIES = {
    "fam_cancel_unshipped",
    "fam_return_delivered_recent",
    "fam_order_lookup_status",
    "fam_auth_valid",
    "fam_hard_multi_order_filter",
    "fam_hard_cross_order_math",
    "fam_hard_item_cancellation",
    "fam_hard_deductive_refund",
    "fam_hard_temporal_mixed",
    "fam_hard_counterfactual_hypothetical",
    "fam_hard_distractor_address",
    "fam_hard_capability_fallback",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOLDOUT_TASKS_FILE = PROJECT_ROOT / "evals" / "tasks.jsonl"
FROZEN_CLOCK = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)


class ValidationError(ValueError):
    """Raised when an SFT example violates schema, security, or contamination rules."""
    pass


def normalize_scenario_template(prompt: str) -> str:
    """
    Strips specific entity slots to extract the underlying structural scenario template.
    Replaces customer IDs, order IDs, PINs, dollar figures, and dates with generic tokens.
    """
    text = prompt.strip()
    text = re.sub(r"\bCUST-\w+\b", "<CUST_ID>", text, flags=re.IGNORECASE)
    text = re.sub(r"\bORD-\w+\b", "<ORDER_ID>", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{4}\b", "<PIN>", text)
    text = re.sub(r"\$\d+(\.\d{2})?", "<AMOUNT>", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z?)?\b", "<DATE>", text)
    text = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "<EMAIL>", text)
    text = re.sub(r"\s+", " ", text).lower()
    return text


def compute_ngram_jaccard(text1: str, text2: str, n: int = 3) -> float:
    """Computes character n-gram Jaccard similarity between two strings."""
    def get_ngrams(s: str) -> set[str]:
        cleaned = re.sub(r"\s+", " ", s.lower().strip())
        if len(cleaned) < n:
            return {cleaned}
        return {cleaned[i:i+n] for i in range(len(cleaned) - n + 1)}

    s1 = get_ngrams(text1)
    s2 = get_ngrams(text2)
    if not s1 or not s2:
        return 0.0
    intersection = len(s1.intersection(s2))
    union = len(s1.union(s2))
    return intersection / union if union > 0 else 0.0


class SFTDatasetValidator:
    """Validates SFT conversation traces against domain security invariants and holdout isolation."""

    def __init__(
        self,
        holdout_path: Path | None = None,
        similarity_threshold: float = 0.70,
        template_threshold: float = 0.75,
    ):
        self.holdout_path = holdout_path or HOLDOUT_TASKS_FILE
        self.similarity_threshold = similarity_threshold
        self.template_threshold = template_threshold
        self.holdout_records: list[dict[str, Any]] = self._load_holdout_records()
        self.valid_tool_names = {t["function"]["name"] for t in TOOL_SCHEMAS}
        self.tool_schemas_by_name = {t["function"]["name"]: t["function"] for t in TOOL_SCHEMAS}

    def _load_holdout_records(self) -> list[dict[str, Any]]:
        records = []
        if self.holdout_path and self.holdout_path.exists():
            for line in self.holdout_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get("split") == "frozen_holdout" or "holdout" in data.get("id", ""):
                            records.append({
                                "id": data.get("id", ""),
                                "family_id": data.get("family_id", ""),
                                "prompt": data.get("user_prompt", ""),
                                "normalized_template": normalize_scenario_template(data.get("user_prompt", "")),
                                "expected_tools": data.get("expected_tool_calls", []),
                            })
                    except Exception:
                        pass

        # Also guard against Stage 4 Hard Reasoning benchmark tasks
        try:
            from runwise.evals.hard_reasoning_generator import generate_8_hard_reasoning_scenarios
            for s in generate_8_hard_reasoning_scenarios():
                records.append({
                    "id": s.task_id,
                    "family_id": s.family_id,
                    "prompt": s.scenario.user_prompt,
                    "normalized_template": normalize_scenario_template(s.scenario.user_prompt),
                    "expected_tools": s.expected.required_tools,
                })
        except Exception:
            pass

        # Also guard against Stage 5 benchmark tasks
        try:
            from runwise.evals.stage5_benchmark import generate_stage5_benchmark_scenarios
            for s in generate_stage5_benchmark_scenarios():
                records.append({
                    "id": s.task_id,
                    "family_id": s.family_id,
                    "prompt": s.scenario.user_prompt,
                    "normalized_template": normalize_scenario_template(s.scenario.user_prompt),
                    "expected_tools": s.expected.required_tools,
                })
        except Exception:
            pass

        return records

    def validate_example(self, example: SFTExample) -> None:
        """
        Runs comprehensive validation on a single SFTExample.
        Raises ValidationError if any check fails.
        """
        # 1. Entity Quarantine Check
        for entity in QUARANTINED_ENTITIES:
            if entity in example.customer_id:
                raise ValidationError(
                    f"Example {example.example_id} violates quarantine: customer_id uses reserved benchmark entity '{entity}'."
                )
            if example.order_id and entity in example.order_id:
                raise ValidationError(
                    f"Example {example.example_id} violates quarantine: order_id uses reserved benchmark entity '{entity}'."
                )
            if entity in example.scenario_prompt:
                raise ValidationError(
                    f"Example {example.example_id} violates quarantine: prompt contains reserved benchmark entity '{entity}'."
                )

        # 2. Contamination: Lexical, Template, & Semantic Near-Duplicates
        norm_example_template = normalize_scenario_template(example.scenario_prompt)
        for holdout in self.holdout_records:
            # 2a. Raw SequenceMatcher
            ratio = difflib.SequenceMatcher(
                None,
                example.scenario_prompt.lower(),
                holdout["prompt"].lower(),
            ).ratio()
            if ratio >= self.similarity_threshold:
                raise ValidationError(
                    f"Example {example.example_id} is contaminated: {ratio:.1%} similarity to "
                    f"frozen holdout task '{holdout['id']}' (threshold {self.similarity_threshold:.1%})."
                )

            # 2b. Slot-Normalized Template Matching
            template_ratio = difflib.SequenceMatcher(
                None,
                norm_example_template,
                holdout["normalized_template"],
            ).ratio()
            if template_ratio >= self.template_threshold:
                raise ValidationError(
                    f"Example {example.example_id} leaks scenario template: {template_ratio:.1%} template "
                    f"similarity to holdout '{holdout['id']}' (threshold {self.template_threshold:.1%})."
                )

            # 2c. Character N-Gram Jaccard Paraphrase Detection
            jaccard_sim = compute_ngram_jaccard(example.scenario_prompt, holdout["prompt"], n=4)
            if jaccard_sim >= 0.65:
                raise ValidationError(
                    f"Example {example.example_id} detected as semantic paraphrase: 4-gram Jaccard "
                    f"{jaccard_sim:.1%} with holdout '{holdout['id']}'."
                )

        # 3. Reserved Task Family Check
        if hasattr(example, "task_family") and example.task_family in RESERVED_TASK_FAMILIES:
            raise ValidationError(
                f"Example {example.example_id} collides with reserved benchmark task family '{example.task_family}'."
            )

        # 4. Message Sequence & Turn Integrity
        if not example.messages:
            raise ValidationError(f"Example {example.example_id} has empty message history.")
        if example.messages[0].role != "system":
            raise ValidationError(f"Example {example.example_id} must start with a system message.")
        if len(example.messages) < 3:
            raise ValidationError(f"Example {example.example_id} has fewer than 3 messages (incomplete interaction).")

        # 5. Security Invariants, Auth Ordering, Policy Transitions, & Credential Leakage
        is_authenticated = False
        seen_tool_call_ids: set[str] = set()
        executed_tool_names: list[str] = []
        order_status_cache: dict[str, dict[str, Any]] = {}

        for idx, msg in enumerate(example.messages):
            # 5a. Credential and Secret Leakage Check
            if msg.role == "assistant" and msg.content:
                lowered_content = msg.content.lower()
                leakage_patterns = [
                    r"\bsqlite://",
                    r"\bpostgres://",
                    r"\bsecret_key\b",
                    r"\bapi_key\b",
                    r"\bauth_token\b",
                    r"verification code for cust-\w+ is \d{4}",
                    r"password is \w+",
                ]
                for pat in leakage_patterns:
                    if re.search(pat, lowered_content):
                        raise ValidationError(
                            f"Example {example.example_id} leaks credentials or internal secrets in assistant message: {msg.content}"
                        )

            # 5b. Assistant Tool Calls
            if msg.role == "assistant" and msg.tool_calls:
                call_names = [tc.function.name for tc in msg.tool_calls]
                executed_tool_names.extend(call_names)

                # Parallel Mutation Invariant: verify_customer + mutation in same turn is strictly forbidden
                if "verify_customer" in call_names and any(cn in PROTECTED_MUTATIONS for cn in call_names):
                    raise ValidationError(
                        f"Example {example.example_id} attempted parallel verification and mutation in turn {idx}: {call_names}. "
                        f"Identity must be verified before initiating mutations."
                    )

                if len(call_names) > 1 and any(cn in PROTECTED_MUTATIONS for cn in call_names):
                    raise ValidationError(
                        f"Example {example.example_id} has parallel mutation calls in turn {idx}: {call_names}. "
                        f"Mutations must be invoked in dedicated sequential steps."
                    )

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    if fn_name not in self.valid_tool_names:
                        raise ValidationError(
                            f"Example {example.example_id} references unknown tool '{fn_name}' in turn {idx}."
                        )

                    schema = self.tool_schemas_by_name[fn_name]
                    required_params = schema.get("parameters", {}).get("required", [])
                    raw_args = tc.function.arguments
                    args_dict = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

                    if not isinstance(args_dict, dict):
                        raise ValidationError(
                            f"Example {example.example_id} has non-dict tool arguments for '{fn_name}': {raw_args}"
                        )

                    for req in required_params:
                        if req not in args_dict:
                            raise ValidationError(
                                f"Example {example.example_id} missing required argument '{req}' for tool '{fn_name}'."
                            )

                    # Mutation without prior authentication check
                    if fn_name in PROTECTED_MUTATIONS and not is_authenticated:
                        raise ValidationError(
                            f"Example {example.example_id} attempted protected mutation '{fn_name}' "
                            f"before customer was verified."
                        )

                    # Impossible Policy Transitions Check
                    target_oid = args_dict.get("order_id")
                    if target_oid and target_oid in order_status_cache:
                        cached_order = order_status_cache[target_oid]
                        c_status = cached_order.get("status")

                        if fn_name == "cancel_order" and c_status in ("shipped", "delivered"):
                            raise ValidationError(
                                f"Example {example.example_id} attempted impossible policy transition: "
                                f"cancel_order on order {target_oid} with status '{c_status}'."
                            )

                        if fn_name == "update_shipping_address" and c_status in ("shipped", "delivered"):
                            raise ValidationError(
                                f"Example {example.example_id} attempted impossible policy transition: "
                                f"update_shipping_address on order {target_oid} with status '{c_status}'."
                            )

                        if fn_name == "issue_refund":
                            if c_status != "delivered":
                                raise ValidationError(
                                    f"Example {example.example_id} attempted impossible policy transition: "
                                    f"issue_refund on non-delivered order {target_oid} (status '{c_status}')."
                                )
                            del_at = cached_order.get("delivered_at")
                            if del_at:
                                try:
                                    dt = datetime.fromisoformat(del_at.replace("Z", "+00:00"))
                                    days_since = (FROZEN_CLOCK - dt).days
                                    if days_since > 30:
                                        raise ValidationError(
                                            f"Example {example.example_id} attempted impossible policy transition: "
                                            f"issue_refund on order {target_oid} delivered {days_since} days ago (>30d window)."
                                        )
                                except Exception as e:
                                    if isinstance(e, ValidationError):
                                        raise

                    seen_tool_call_ids.add(tc.id)

            # 5c. Tool Responses & Anti-Fabrication Check
            elif msg.role == "tool":
                if not msg.tool_call_id or msg.tool_call_id not in seen_tool_call_ids:
                    raise ValidationError(
                        f"Example {example.example_id} has orphaned tool result with ID '{msg.tool_call_id}'."
                    )

                try:
                    tool_content = json.loads(msg.content or "{}")
                    if not isinstance(tool_content, dict) or "success" not in tool_content:
                        raise ValidationError(
                            f"Example {example.example_id} has invalid/fabricated tool return format: {msg.content}"
                        )
                    if "data" not in tool_content:
                        raise ValidationError(
                            f"Example {example.example_id} tool return missing standard 'data' field: {msg.content}"
                        )

                    # Track verified customer
                    if msg.name == "verify_customer":
                        if tool_content.get("success") is True:
                            is_authenticated = True
                        else:
                            is_authenticated = False

                    # Cache order data for transition validation
                    if msg.name == "lookup_order" and tool_content.get("success") is True:
                        odata = tool_content.get("data", {}).get("order", {})
                        if odata.get("order_id"):
                            order_status_cache[odata["order_id"]] = odata

                except json.JSONDecodeError:
                    raise ValidationError(
                        f"Example {example.example_id} has non-JSON tool return content: {msg.content}"
                    )

        # 6. Expected Tool Trajectory Clone Check
        for holdout in self.holdout_records:
            h_tools = holdout.get("expected_tools")
            if h_tools and h_tools == executed_tool_names:
                ratio = difflib.SequenceMatcher(None, example.scenario_prompt.lower(), holdout["prompt"].lower()).ratio()
                if ratio >= 0.60:
                    raise ValidationError(
                        f"Example {example.example_id} matches exact tool trajectory {executed_tool_names} "
                        f"and has high similarity ({ratio:.1%}) to holdout '{holdout['id']}'."
                    )

    def validate_dataset(self, examples: list[SFTExample]) -> dict[str, Any]:
        """
        Validates an entire batch of SFT examples.
        Returns summary metrics or raises ValidationError on first breach.
        """
        seen_ids = set()
        domain_counts: dict[str, int] = {}

        for ex in examples:
            if ex.example_id in seen_ids:
                raise ValidationError(f"Duplicate example_id detected: '{ex.example_id}'.")
            seen_ids.add(ex.example_id)

            self.validate_example(ex)

            domain = ex.curriculum_domain
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        return {
            "total_validated": len(examples),
            "unique_example_ids": len(seen_ids),
            "curriculum_distribution": domain_counts,
            "status": "PASSED",
        }
