"""
Cost-Aware Semantic Auto-Router for Runwise Agent Service.

Evaluates user prompt complexity, policy risk, and semantic ambiguity
to route queries between cost-effective (Flash) and frontier (Pro) models.
Operates with sub-millisecond overhead without auxiliary LLM calls.
"""

from __future__ import annotations

import re
import time
from typing import Any
from pydantic import BaseModel, Field


class AutoRouterConfig(BaseModel):
    """Configuration parameters for the AutoRouter."""
    enabled: bool = True
    cheap_model: str = "vertex_ai/gemini-2.5-flash"
    strong_model: str = "vertex_ai/gemini-2.5-pro"
    complexity_threshold: float = Field(default=0.45, ge=0.0, le=1.0)


class RoutingDecision(BaseModel):
    """Structured decision produced by the AutoRouter."""
    selected_model: str
    complexity_score: float
    decision_reason: str
    features_detected: list[str]
    latency_overhead_ms: float


# Regex patterns indicating high-risk or complex workflows
ADVERSARIAL_PATTERNS = [
    r"(?i)\b(ignore|disregard|override)\b.*?\b(previous|system|all)\b.*?\b(instructions|rules|prompt)\b",
    r"(?i)\b(system\s*prompt|internal\s*instructions|developer\s*mode|jailbreak)\b",
    r"(?i)\b(bypass|pretend|roleplay|hypothetical)\b",
    r"(?i)\b(forget\s+your\s+training|sudo\s+mode)\b",
]

HIGH_LIABILITY_PATTERNS = [
    r"(?i)\b(refund|return|compensation|damaged|stolen|fraud|chargeback)\b",
    r"(?i)\b(lawsuit|attorney|legal\s*action|complaint)\b",
]

MULTI_ENTITY_PATTERNS = [
    r"(?i)\b(both|neither|either|multiple|several)\b",
    r"ORD-\d+.*?ORD-\d+",  # References to multiple order IDs
]


class AutoRouter:
    """
    Sub-millisecond semantic complexity analyzer and model selector.
    """

    def __init__(self, config: AutoRouterConfig | None = None) -> None:
        self.config = config or AutoRouterConfig()

    def route(self, prompt: str, metadata: dict[str, Any] | None = None) -> RoutingDecision:
        t0 = time.perf_counter()
        features: list[str] = []
        score = 0.0

        clean_text = prompt.strip()
        length = len(clean_text)

        # 1. Adversarial & Prompt Injection Risk (+0.60)
        for pattern in ADVERSARIAL_PATTERNS:
            if re.search(pattern, clean_text):
                score += 0.60
                features.append("adversarial_risk")
                break

        # 2. High-Liability Financial / Dispute Transactions (+0.35)
        for pattern in HIGH_LIABILITY_PATTERNS:
            if re.search(pattern, clean_text):
                score += 0.50
                features.append("financial_dispute")
                break

        # 3. Multi-Entity / Complex Conditional Logic (+0.25)
        for pattern in MULTI_ENTITY_PATTERNS:
            if re.search(pattern, clean_text):
                score += 0.50
                features.append("multi_entity_complexity")
                break

        # 4. Long / Multi-Clause Input (> 250 characters) (+0.15)
        if length > 250:
            score += 0.15
            features.append("high_token_length")

        # 5. Happy-Path Inquiry Discount (-0.30)
        # If user is asking simple tracking or FAQs with clean syntax
        if re.search(r"(?i)\b(status|tracking|where\s+is|hours|policy)\b", clean_text) and not features:
            score = max(0.0, score - 0.30)
            features.append("standard_inquiry_discount")

        # Bound score between 0.0 and 1.0
        final_score = min(1.0, max(0.0, score))

        if final_score >= self.config.complexity_threshold:
            selected_model = self.config.strong_model
            reason = f"Complexity score {final_score:.2f} >= threshold {self.config.complexity_threshold:.2f}"
        else:
            selected_model = self.config.cheap_model
            reason = f"Complexity score {final_score:.2f} < threshold {self.config.complexity_threshold:.2f}"

        overhead_ms = (time.perf_counter() - t0) * 1000.0

        return RoutingDecision(
            selected_model=selected_model,
            complexity_score=round(final_score, 2),
            decision_reason=reason,
            features_detected=features,
            latency_overhead_ms=round(overhead_ms, 3),
        )
