"""
Trusted, server-controlled financial action authorization and intent classification.

Enforces strict separation between customer identity verification and financial action
authorization. Informational inquiries cannot unilaterally trigger database mutations.
Mutations require either explicit customer transaction instructions or trusted,
server-controlled action confirmations with single-use replay prevention.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class ActionScope(str, Enum):
    """Scope of authorized action: full order vs partial line item vs ambiguous."""
    FULL_ORDER = "FULL_ORDER"
    PARTIAL_ITEM = "PARTIAL_ITEM"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass
class PendingAction:
    """
    Server-staged financial mutation awaiting trusted customer confirmation.
    Captures full policy snapshot and exact financial details.
    """

    action_id: str
    action_type: str  # "issue_refund", "cancel_order", "update_shipping_address"
    order_id: str
    customer_id: str
    amount_cents: int | None = None
    scope: ActionScope = ActionScope.FULL_ORDER
    details: dict[str, Any] = field(default_factory=dict)
    policy_snapshot: dict[str, Any] = field(default_factory=dict)
    created_at_iso: str = ""
    status: ActionStatus = ActionStatus.PENDING
    confirmation_token: str = field(default_factory=lambda: f"tok_{uuid.uuid4().hex[:16]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "amount_cents": self.amount_cents,
            "scope": self.scope.value if isinstance(self.scope, ActionScope) else str(self.scope),
            "status": self.status.value if isinstance(self.status, ActionStatus) else str(self.status),
            "policy_snapshot": self.policy_snapshot,
            "details": self.details,
            "created_at_iso": self.created_at_iso,
        }


@dataclass
class RequestIntent:
    """Classified intent of a customer request."""

    is_explicit_transaction: bool
    intent_type: str  # "EXPLICIT_TRANSACTION" | "INFORMATIONAL_INQUIRY"
    authorized_actions: set[tuple[str, str]] = field(default_factory=set)  # {(action_type, order_id), ...}
    action_scope: ActionScope = ActionScope.FULL_ORDER
    reason: str = ""


# Regex patterns identifying order IDs
ORDER_ID_PATTERN = re.compile(r"\b(ORD-\d{3,4})\b", re.IGNORECASE)

# Negation patterns: customer explicitly states they do NOT want a refund/cancellation
NEGATION_PATTERNS = [
    re.compile(r"\b(?:do\s+not|don't)\s+(?:want\s+a\s+)?(?:refund|cancel|alter)\b", re.IGNORECASE),
    re.compile(r"\b(?:not\s+requesting|not\s+asking\s+for)\s+(?:a\s+)?(?:refund|compensation|chargeback)\b", re.IGNORECASE),
    re.compile(r"\bplease\s+do\s+not\s+refund\b", re.IGNORECASE),
]

# Hypothetical and counterfactual patterns: customer asks about potential policy outcomes without ordering an immediate mutation
HYPOTHETICAL_PATTERNS = [
    re.compile(r"\bsuppose\s+i\s+(?:wanted|needed|tried|decided)\s+to\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+if\s+i\s+(?:wanted|needed|tried)\s+to\b", re.IGNORECASE),
    re.compile(r"\bif\s+i\s+(?:were|was)\s+to\b", re.IGNORECASE),
    re.compile(r"\bhypothetically\b", re.IGNORECASE),
]

# Open-ended inquiry / diagnostic questions without directive financial commands
AMBIGUOUS_INQUIRY_PATTERNS = [
    re.compile(r"\bwhat\s+can\s+you\s+do\s+for\s+me\b", re.IGNORECASE),
    re.compile(r"\bhow\s+do\s+you\s+handle\s+this\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:are\s+)?(?:my\s+|the\s+)?options\b", re.IGNORECASE),
    re.compile(r"\bhow\s+does\s+(?:this|your\s+policy)\s+work\b", re.IGNORECASE),
    re.compile(r"\b(?:can\s+you\s+)?(?:explain|clarify)\s+why\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+is\s+your\s+(?:return|refund|cancellation)\s+policy\b", re.IGNORECASE),
    re.compile(r"\b(?:refund|return|cancellation)\s+(?:window|policy|timeline|rules|status|eligibility)\b", re.IGNORECASE),
    re.compile(r"\bwithin\s+(?:your\s+)?(?:\d+-day\s+)?(?:refund|return)\s+window\b", re.IGNORECASE),
    re.compile(r"\baccounting\s+of\s+(?:my\s+)?purchase\s+history\b", re.IGNORECASE),
]

# Affirmative financial and mutation transaction directives
REFUND_COMMAND_PATTERNS = [
    re.compile(r"\b(?:please\s+)?(?:issue|give|process|provide|execute)\s+(?:me\s+)?(?:a\s+)?(?:full\s+|partial\s+)?(?:\$?\d+(?:\.\d{2})?\s+)?refund\b", re.IGNORECASE),
    re.compile(r"\b(?:instruct|authorize)\s+(?:you\s+to\s+)?(?:issue|process)\s+(?:a\s+)?(?:full\s+|partial\s+)?(?:\$?\d+(?:\.\d{2})?\s+)?refund\b", re.IGNORECASE),
    re.compile(r"\brefund\s+(?:my\s+|the\s+)?order\b", re.IGNORECASE),
    re.compile(r"\brefund\s+(?:the\s+remaining\s+)?\$?\d+", re.IGNORECASE),
    re.compile(r"\b(?:requesting|want|need|would\s+like)\s+(?:a\s+)?(?:full\s+|partial\s+)?(?:\$?\d+(?:\.\d{2})?\s+)?refund\b", re.IGNORECASE),
    re.compile(r"\b(?:full|partial)\s+refund\s+of\s+\$?\d+\b", re.IGNORECASE),
    re.compile(r"\b(?:process|issue)\s+refunds?\b", re.IGNORECASE),
]

CANCEL_COMMAND_PATTERNS = [
    re.compile(r"\b(?:please\s+)?(?:cancel|abort|stop)\s+(?:my\s+|the\s+)?(?:pending\s+|entire\s+)?order\b", re.IGNORECASE),
    re.compile(r"\bcancel\s+ORD-\d+\b", re.IGNORECASE),
    re.compile(r"\bcancel\s+(?:it|this)(?:\s+immediately)?\b", re.IGNORECASE),
    re.compile(r"\b(?:need|want|would like|proceed with)\s+(?:to\s+cancel|cancelling)\b", re.IGNORECASE),
    re.compile(r"\b(?:want|need|have)\s+(?:the\s+)?(?:entire\s+)?order\s+cancelled\b", re.IGNORECASE),
    re.compile(r"\border\s+(?:to\s+be\s+)?cancelled\b", re.IGNORECASE),
]

AMBIGUOUS_SCOPE_PATTERNS = [
    re.compile(r"\bcancel\s+(?:part|portion|something|some\s+items?)\b", re.IGNORECASE),
    re.compile(r"\bpartial\s+order\b", re.IGNORECASE),
]

PARTIAL_CANCEL_PATTERNS = [
    re.compile(r"\b(?:cancel|drop|remove)\s+(?:only|just)\b", re.IGNORECASE),
    re.compile(r"\b(?:leave|keep)\s+(?:the\s+)?(?:other|rest|remaining|item)\b", re.IGNORECASE),
    re.compile(r"\bpartial\s+cancellation\b", re.IGNORECASE),
    re.compile(r"\bcancel\s+(?:one|single)\s+item\b", re.IGNORECASE),
    re.compile(r"\bcancel\s+(?:a\s+)?specific\s+item\b", re.IGNORECASE),
]

ADDRESS_COMMAND_PATTERNS = [
    re.compile(r"\b(?:update|change|modify)\s+(?:the\s+|my\s+)?(?:delivery\s+|shipping\s+)?address\b", re.IGNORECASE),
]


def classify_request_intent(prompt: str) -> RequestIntent:
    """
    Deterministically classifies whether a user prompt represents an explicit
    transaction instruction or an informational/ambiguous inquiry.

    Invariants:
    1. Negations ("do not refund", "not requesting compensation") always classify as INFORMATIONAL_INQUIRY.
    2. Open-ended inquiries ("What can you do for me?", "How do you handle this?") without affirmative
       transaction directives classify as INFORMATIONAL_INQUIRY.
    3. Explicit imperatives ("Please cancel ORD-101", "Refund $50 on ORD-103") extract the targeted
       orders and classify as EXPLICIT_TRANSACTION with scoped authorization.
    """
    prompt_clean = prompt.strip()
    order_matches = set(m.upper() for m in ORDER_ID_PATTERN.findall(prompt_clean))

    # 1. Check for explicit negations
    for neg_pat in NEGATION_PATTERNS:
        if neg_pat.search(prompt_clean):
            return RequestIntent(
                is_explicit_transaction=False,
                intent_type="INFORMATIONAL_INQUIRY",
                authorized_actions=set(),
                reason="Prompt explicitly negates refund or cancellation action.",
            )

    # 2. Check for hypothetical / counterfactual questions
    for hyp_pat in HYPOTHETICAL_PATTERNS:
        if hyp_pat.search(prompt_clean):
            return RequestIntent(
                is_explicit_transaction=False,
                intent_type="INFORMATIONAL_INQUIRY",
                authorized_actions=set(),
                reason="Prompt poses a hypothetical inquiry rather than an immediate transaction directive.",
            )

    # 3. Check for ambiguous scope or partial item cancellation
    # Invariant: A user request to cancel one item must never authorize whole-order cancellation.
    is_ambiguous_scope = any(p.search(prompt_clean) for p in AMBIGUOUS_SCOPE_PATTERNS)
    is_partial_cancel = any(p.search(prompt_clean) for p in PARTIAL_CANCEL_PATTERNS)

    if is_ambiguous_scope:
        return RequestIntent(
            is_explicit_transaction=False,
            intent_type="INFORMATIONAL_INQUIRY",
            authorized_actions=set(),
            action_scope=ActionScope.AMBIGUOUS,
            reason="Prompt cancellation scope is ambiguous; whole-order cancellation is unauthorized.",
        )

    if is_partial_cancel:
        return RequestIntent(
            is_explicit_transaction=False,
            intent_type="INFORMATIONAL_INQUIRY",
            authorized_actions=set(),
            action_scope=ActionScope.PARTIAL_ITEM,
            reason="Prompt requests partial item cancellation; whole-order cancellation is unauthorized.",
        )

    # 4. Check for open-ended ambiguous inquiries
    is_ambiguous = any(inq_pat.search(prompt_clean) for inq_pat in AMBIGUOUS_INQUIRY_PATTERNS)

    # 5. Check for affirmative transaction directives
    authorized_actions: set[tuple[str, str]] = set()

    has_refund_command = any(p.search(prompt_clean) for p in REFUND_COMMAND_PATTERNS)
    has_cancel_command = any(p.search(prompt_clean) for p in CANCEL_COMMAND_PATTERNS)
    has_address_command = any(p.search(prompt_clean) for p in ADDRESS_COMMAND_PATTERNS)

    # If the prompt is an ambiguous inquiry and lacks affirmative transaction commands
    if is_ambiguous and not (has_refund_command or has_cancel_command or has_address_command):
        return RequestIntent(
            is_explicit_transaction=False,
            intent_type="INFORMATIONAL_INQUIRY",
            authorized_actions=set(),
            reason="Prompt is an ambiguous inquiry requesting options or explanation without transaction directive.",
        )

    # Associate commands with targeted order IDs
    if has_refund_command:
        for oid in order_matches:
            authorized_actions.add(("issue_refund", oid))
        if not order_matches:
            authorized_actions.add(("issue_refund", "*"))

    if has_cancel_command:
        for oid in order_matches:
            authorized_actions.add(("cancel_order", oid))
        if not order_matches:
            authorized_actions.add(("cancel_order", "*"))

    if has_address_command:
        for oid in order_matches:
            authorized_actions.add(("update_shipping_address", oid))
        if not order_matches:
            authorized_actions.add(("update_shipping_address", "*"))

    if authorized_actions:
        return RequestIntent(
            is_explicit_transaction=True,
            intent_type="EXPLICIT_TRANSACTION",
            authorized_actions=authorized_actions,
            reason="Prompt contains explicit directive for order mutation.",
        )

    # Default fallback: If it's a general question or inquiry
    return RequestIntent(
        is_explicit_transaction=False,
        intent_type="INFORMATIONAL_INQUIRY",
        authorized_actions=set(),
        reason="No affirmative transaction command detected; treated as informational inquiry.",
    )
