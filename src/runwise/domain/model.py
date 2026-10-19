from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import TYPE_CHECKING, Any
from pydantic import BaseModel

if TYPE_CHECKING:
    from runwise.domain.authorization import PendingAction


class ToolResult(BaseModel):
    """Standardized response schema returned by every domain tool."""
    success: bool
    error_code: str | None = None     # e.g., 'AUTH_REQUIRED', 'ORDER_SHIPPED', 'LIMIT_EXCEEDED'
    data: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class SessionContext:
    """Carries trial execution state, database connection, and session authorization."""
    conn: sqlite3.Connection
    trial_id: str
    current_time_iso: str             # Deterministic injected clock (e.g. '2026-10-15T12:00:00Z')
    authenticated_user_id: str | None = None  # Populated only after successful verify_customer

    # Trusted Server-Controlled Action Authorization State
    pending_actions: dict[str, PendingAction] = field(default_factory=dict)
    consumed_action_tokens: set[str] = field(default_factory=set)
    authorized_explicit_actions: set[tuple[str, str]] = field(default_factory=set)
    action_scopes: dict[tuple[str, str], Any] = field(default_factory=dict)
    request_intent: str = "EXPLICIT_TRANSACTION"

    def is_authorized(self, user_id: str) -> bool:
        """Returns True if the active session is authenticated for the requested user_id."""
        return self.authenticated_user_id is not None and self.authenticated_user_id == user_id

    def authorize_action(self, action_type: str, order_id: str, scope: Any = None) -> None:
        """
        Grants explicit transaction authorization for a specific action and order.
        Explicitly binds full-order scope if scope is not otherwise specified.
        """
        from runwise.domain.authorization import ActionScope

        self.authorized_explicit_actions.add((action_type, order_id))
        if order_id != "*":
            resolved_scope = scope if scope is not None else ActionScope.FULL_ORDER
            self.set_action_scope(action_type, order_id, resolved_scope, force=True)

    def set_action_scope(self, action_type: str, order_id: str, scope: Any, force: bool = False) -> None:
        """
        Sets the trusted action scope for an action on an order.
        Invariants:
        - If existing scope is PARTIAL_ITEM or AMBIGUOUS, it cannot be downgraded or silently
          overwritten to FULL_ORDER without explicit force/confirmation.
        - None, invalid strings, or unrecognized objects fail closed to None.
        """
        from runwise.domain.authorization import ActionScope

        resolved_scope: ActionScope | None
        if isinstance(scope, ActionScope):
            resolved_scope = scope
        elif isinstance(scope, str):
            try:
                resolved_scope = ActionScope(scope)
            except ValueError:
                resolved_scope = None
        else:
            resolved_scope = None

        existing = self.action_scopes.get((action_type, order_id))
        if (
            existing in (ActionScope.PARTIAL_ITEM, ActionScope.AMBIGUOUS)
            and resolved_scope == ActionScope.FULL_ORDER
            and not force
        ):
            # Prevent silent overwrite of a restricted/partial scope to full order
            return

        self.action_scopes[(action_type, order_id)] = resolved_scope

    def get_action_scope(self, action_type: str, order_id: str) -> Any:
        """
        Returns the trusted action scope bound to the exact action_type and order_id.
        FAILS CLOSED: Returns None if absent, unset, or invalid. Never defaults to FULL_ORDER.
        Wildcards are NOT permitted to grant action scope.
        """
        from runwise.domain.authorization import ActionScope

        scope = self.action_scopes.get((action_type, order_id))
        if scope is None:
            return None
        if isinstance(scope, ActionScope):
            return scope
        try:
            return ActionScope(scope)
        except (ValueError, TypeError):
            return None

    def stage_pending_action(self, action: PendingAction) -> str:
        """Stores a server-staged pending action awaiting trusted confirmation."""
        self.pending_actions[action.action_id] = action
        return action.action_id

    def confirm_pending_action(
        self,
        action_id: str,
        confirmation_token: str,
        *,
        expected_order_id: str | None = None,
        expected_amount_cents: int | None = None,
        expected_scope: Any | None = None,
        expected_customer_id: str | None = None,
    ) -> bool:
        """
        Trusted application/session method to confirm a pending financial action.
        Validates token, ensures single-use, binds to exact order, customer, and amount,
        and marks CONFIRMED.
        Cannot be called by LLM-generated arguments.
        """
        from runwise.domain.authorization import ActionStatus

        action = self.pending_actions.get(action_id)
        if not action:
            raise ValueError(f"Action '{action_id}' not found.")
        if action.status == ActionStatus.EXECUTED or action.confirmation_token in self.consumed_action_tokens:
            raise ValueError(f"Action '{action_id}' has already been executed/consumed (replay prevented).")
        if action.status != ActionStatus.PENDING:
            raise ValueError(f"Action '{action_id}' is not in PENDING state (current: {action.status}).")
        if action.confirmation_token != confirmation_token:
            raise ValueError("Invalid confirmation token.")
        if expected_order_id and action.order_id != expected_order_id:
            raise ValueError(f"Confirmation order mismatch: expected {expected_order_id}, got {action.order_id}.")
        if expected_customer_id and action.customer_id != expected_customer_id:
            raise ValueError(f"Confirmation customer mismatch: expected {expected_customer_id}, got {action.customer_id}.")
        if expected_amount_cents is not None and action.amount_cents != expected_amount_cents:
            raise ValueError(f"Confirmation amount mismatch: expected {expected_amount_cents}, got {action.amount_cents}.")
        if expected_scope is not None and getattr(action, "scope", None) != expected_scope:
            raise ValueError(f"Confirmation scope mismatch: expected {expected_scope}, got {getattr(action, 'scope', None)}.")

        action.status = ActionStatus.CONFIRMED
        if getattr(action, "scope", None) is not None:
            self.set_action_scope(action.action_type, action.order_id, action.scope, force=True)
        return True

    def get_confirmed_action(
        self,
        action_type: str,
        order_id: str,
        amount_cents: int | None = None,
        scope: Any | None = None,
    ) -> PendingAction | None:
        """
        Returns a confirmed pending action matching the exact action_type, order_id, and amount.
        Enforces exact order ID binding, customer isolation, and prevents replay.
        Returns None if not found or already consumed.
        """
        from runwise.domain.authorization import ActionStatus

        for action in self.pending_actions.values():
            if (
                action.action_type == action_type
                and action.order_id == order_id  # Exact order ID required
                and action.status == ActionStatus.CONFIRMED
                and action.confirmation_token not in self.consumed_action_tokens
            ):
                if self.authenticated_user_id and action.customer_id != self.authenticated_user_id:
                    continue
                if amount_cents is not None and action.amount_cents is not None and action.amount_cents != amount_cents:
                    continue
                if scope is not None and getattr(action, "scope", None) != scope:
                    continue
                return action
        return None

    def consume_confirmed_action(self, action: PendingAction) -> None:
        """Marks a confirmed pending action as EXECUTED and records token consumption to prevent replay."""
        from runwise.domain.authorization import ActionStatus

        action.status = ActionStatus.EXECUTED
        self.consumed_action_tokens.add(action.confirmation_token)

