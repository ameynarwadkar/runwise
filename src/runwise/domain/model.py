from dataclasses import dataclass
import sqlite3
from typing import Any
from pydantic import BaseModel


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

    def is_authorized(self, user_id: str) -> bool:
        """Returns True if the active session is authenticated for the requested user_id."""
        return self.authenticated_user_id is not None and self.authenticated_user_id == user_id
