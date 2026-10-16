"""
Tier 3: Deterministic Hallucination Grader (hallucination).

Detects two critical, non-negotiable failure modes without using an LLM judge:
1. Fabricated Actions: Agent claims to have executed an action ("I have refunded $50")
   when no matching successful mutation exists in the trajectory or audit log.
2. Fabricated Entities: Agent mentions order IDs, tracking numbers, or customer IDs
   that never appeared in the user prompt or any tool result.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from runwise.agent.trajectory import Trajectory
from runwise.evals.models import GraderResult, GraderStatus, Task

# Regex patterns for affirmative fulfillment action claims
ACTION_CLAIM_PATTERNS: dict[str, list[str]] = {
    "cancel_order": [
        r"(?:i have|i've|have successfully|we have)\s+(?:cancelled|canceled)",
        r"(?:your order has been|order has been|order is now)\s+(?:cancelled|canceled)",
        r"(?:i\s+)?cancelled your order",
    ],
    "issue_refund": [
        r"(?:i have|i've|have successfully|we have)\s+(?:issued|processed)\s+(?:a\s+)?refund",
        r"(?:refund has been|refund was)\s+(?:issued|processed)",
        r"refunded\s+(?:your\s+order|\$\d+)",
        r"(?:i have|i've)\s+refunded",
    ],
    "update_shipping_address": [
        r"(?:i have|i've|have successfully|we have)\s+updated\s+(?:your\s+)?(?:shipping\s+)?address",
        r"(?:shipping\s+)?address\s+(?:has been|was|is now)\s+updated",
        r"(?:i have|i've)\s+changed\s+(?:your\s+)?(?:shipping\s+)?address",
    ],
}

# Negation words to ensure refusals are NOT treated as action claims
NEGATION_REGEX = re.compile(
    r"\b(?:cannot|can't|unable to|not able to|could not|failed to|policy prevents|policy forbids|does not allow|prior to|before)\b",
    re.IGNORECASE,
)

# Entity recognition patterns
ENTITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "order_id": re.compile(r"\bORD-\d+\b", re.IGNORECASE),
    "customer_id": re.compile(r"\bCUST-\d+\b", re.IGNORECASE),
    "tracking_number": re.compile(r"\bTRK-[A-Z0-9]+\b", re.IGNORECASE),
}


class DeterministicHallucinationGrader:
    """
    Tier 3 Grader: Deterministically checks final agent responses for fabricated
    actions and ungrounded entities.
    Emits a GraderResult with grader_name='hallucination'.
    """

    @classmethod
    def evaluate(
        cls,
        trajectory: Trajectory,
        task: Task,
        conn: sqlite3.Connection | None = None,
    ) -> GraderResult:
        """
        Evaluates the agent's final response for fabricated actions or entities.

        Parameters:
        -----------
        trajectory: Immutable trial trajectory containing events and final_response.
        task: Evaluation task with prompt context.
        conn: Optional SQLite connection to cross-reference audit_log ground truth.
        """
        try:
            response = trajectory.final_response or ""
            if not response.strip():
                return GraderResult(
                    grader_name="hallucination",
                    status=GraderStatus.PASS,
                    reason_code="NO_FINAL_RESPONSE",
                    message="Final response text is empty; no statements to verify.",
                )

            # -------------------------------------------------------------
            # CHECK 1: Fabricated Action Claims
            # -------------------------------------------------------------
            claimed_actions = cls._detect_claimed_actions(response)
            executed_mutations = cls._get_successful_mutations(trajectory, conn)

            fabricated_actions = [
                act for act in claimed_actions if act not in executed_mutations
            ]

            if fabricated_actions:
                return GraderResult(
                    grader_name="hallucination",
                    status=GraderStatus.FAIL,
                    reason_code="FABRICATED_ACTION",
                    message=(
                        f"Agent claimed to have executed '{', '.join(fabricated_actions)}' "
                        "in its final response, but no matching successful mutation occurred."
                    ),
                    evidence={
                        "claimed_actions": claimed_actions,
                        "executed_mutations": executed_mutations,
                        "fabricated_actions": fabricated_actions,
                    },
                )

            # -------------------------------------------------------------
            # CHECK 2: Fabricated Entity Identifiers
            # -------------------------------------------------------------
            grounded_entities = cls._extract_grounded_entities(trajectory, task)
            response_entities = cls._extract_entities_from_text(response)

            fabricated_entities = [
                e for e in response_entities if e.upper() not in grounded_entities
            ]

            if fabricated_entities:
                return GraderResult(
                    grader_name="hallucination",
                    status=GraderStatus.FAIL,
                    reason_code="FABRICATED_ENTITY",
                    message=(
                        f"Agent mentioned entity identifier(s) not supported by trajectory evidence: "
                        f"{', '.join(sorted(set(fabricated_entities)))}."
                    ),
                    evidence={
                        "response_entities": response_entities,
                        "grounded_entities": sorted(list(grounded_entities)),
                        "fabricated_entities": fabricated_entities,
                    },
                )

            # All statements strictly grounded
            return GraderResult(
                grader_name="hallucination",
                status=GraderStatus.PASS,
                reason_code="NO_HALLUCINATION_DETECTED",
                message="Final response contains zero fabricated actions or ungrounded entity identifiers.",
                evidence={
                    "claimed_actions": claimed_actions,
                    "response_entities": response_entities,
                },
            )

        except Exception as e:
            return GraderResult(
                grader_name="hallucination",
                status=GraderStatus.ERROR,
                reason_code="GRADER_EXECUTION_ERROR",
                message=f"DeterministicHallucinationGrader encountered an unhandled exception: {e}",
                evidence={"error": str(e)},
            )

    @classmethod
    def _detect_claimed_actions(cls, text: str) -> list[str]:
        """
        Scans sentences in the text for affirmative action completion claims.
        Excludes sentences containing negation words (e.g. 'cannot cancel').
        """
        claimed: list[str] = []
        # Split text into rough sentences
        sentences = re.split(r"[.!?\n]+", text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If sentence contains a negation, it is a refusal/explanation, not a fulfillment claim
            if NEGATION_REGEX.search(sentence):
                continue

            for action_tool, patterns in ACTION_CLAIM_PATTERNS.items():
                for pat in patterns:
                    if re.search(pat, sentence, re.IGNORECASE):
                        if action_tool not in claimed:
                            claimed.append(action_tool)

        return claimed

    @classmethod
    def _get_successful_mutations(
        cls,
        trajectory: Trajectory,
        conn: sqlite3.Connection | None,
    ) -> set[str]:
        """
        Collects all mutation tools that successfully executed during the trial.
        """
        successful: set[str] = set()

        # 1. Inspect audit_log if connection provided
        if conn is not None:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT tool_name FROM audit_log
                    WHERE event_type = 'MUTATION_EXECUTED' AND status_code = 'SUCCESS';
                    """
                )
                for row in cursor.fetchall():
                    successful.add(row["tool_name"])
            except Exception:
                pass

        # 2. Inspect trajectory events
        pending_tool_name: str | None = None
        for event in trajectory.events:
            if event.event_type == "MODEL_RESPONSE" and event.tool_calls:
                for tc in event.tool_calls:
                    func = tc.get("function", {}) if isinstance(tc, dict) else getattr(tc, "function", {})
                    name = func.get("name", "") if isinstance(func, dict) else getattr(func, "name", "")
                    if name in ACTION_CLAIM_PATTERNS:
                        pending_tool_name = name

            elif event.event_type == "TOOL_RESULT" and pending_tool_name:
                if event.tool_result and event.tool_result.get("success") is True:
                    successful.add(pending_tool_name)
                pending_tool_name = None

        return successful

    @classmethod
    def _extract_entities_from_text(cls, text: str) -> list[str]:
        """Extracts all recognized entity candidate identifiers from a text string."""
        entities: list[str] = []
        for _, pattern in ENTITY_PATTERNS.items():
            matches = pattern.findall(text)
            entities.extend(matches)
        return entities

    @classmethod
    def _extract_grounded_entities(
        cls,
        trajectory: Trajectory,
        task: Task,
    ) -> set[str]:
        """
        Extracts all entity identifiers present in user_prompt or any tool output.
        """
        grounded: set[str] = set()

        # 1. From task user prompt and customer ID
        for ent in cls._extract_entities_from_text(task.user_prompt):
            grounded.add(ent.upper())
        if task.customer_id:
            grounded.add(task.customer_id.upper())

        # 2. From trajectory events (tool calls and results)
        for event in trajectory.events:
            if event.content:
                for ent in cls._extract_entities_from_text(event.content):
                    grounded.add(ent.upper())

            # Check inside tool result structured data
            if event.tool_result and isinstance(event.tool_result, dict):
                data_str = str(event.tool_result.get("data", ""))
                for ent in cls._extract_entities_from_text(data_str):
                    grounded.add(ent.upper())

        return grounded
