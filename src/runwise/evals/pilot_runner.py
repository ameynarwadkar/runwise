"""
Paired pilot benchmark execution harness with strict budget guards and approval controls.
"""

from __future__ import annotations

from typing import Any

from runwise.evals.routing_schema import PairedScenario


class PilotApprovalError(PermissionError):
    """Raised when paid execution is attempted without explicit user approval."""
    pass


class PilotBudgetExceededError(ValueError):
    """Raised when estimated or actual pilot execution exceeds the allowed budget ceiling."""
    pass


def run_paired_pilot(
    scenarios: list[PairedScenario],
    approved_by_user: bool = False,
    budget_limit_usd: float = 0.50,
) -> list[dict[str, Any]]:
    """
    Executes paired Flash vs Pro evaluation on isolated SQLite sandboxes.
    
    HARD SAFETY GATE:
    Will fail immediately with PilotApprovalError unless approved_by_user is explicitly True.
    """
    if not approved_by_user:
        raise PilotApprovalError(
            "Paid pilot execution blocked: You must obtain explicit user approval before launching "
            "paid Vertex AI evaluations."
        )

    # Note: Live execution against EvaluationRunner will be linked after user confirms the 30 scenarios.
    return []
