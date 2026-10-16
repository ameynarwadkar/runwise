"""
Factory and manager for isolated, in-memory SQLite sandbox databases.

Each trial in an evaluation run receives a completely separate in-memory database,
guaranteeing 0% state leakage between parallel or sequential trials.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

# Resolve standard paths relative to this file
PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
DEFAULT_SEED_PATH = PACKAGE_ROOT / "data" / "fixtures" / "base_seed.sql"


class SandboxDB:
    """Manages ephemeral SQLite sandboxes for agent trials."""

    @classmethod
    def create_connection(
        cls,
        schema_path: Path | None = None,
        seed_path: Path | None = None,
    ) -> sqlite3.Connection:
        """
        Creates a fresh, isolated in-memory SQLite database.
        
        1. Connects to ':memory:' (private to the caller).
        2. Enables PRAGMA foreign_keys = ON (essential, as SQLite disables this by default).
        3. Configures row_factory = sqlite3.Row for dict-like row access.
        4. Executes schema.sql to build tables and constraints.
        5. Optionally executes base_seed.sql to seed initial ground-truth records.
        """
        schema_file = schema_path or DEFAULT_SCHEMA_PATH
        seed_file = seed_path or DEFAULT_SEED_PATH

        # In SQLite, ':memory:' creates a completely unique, thread-safe memory database
        conn = sqlite3.connect(":memory:")
        
        # Enforce foreign keys on this new connection
        conn.execute("PRAGMA foreign_keys = ON;")
        
        # Enable column-name access (e.g. row["status"] instead of row[3])
        conn.row_factory = sqlite3.Row

        # Initialize schema DDL
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found at: {schema_file}")
        conn.executescript(schema_file.read_text(encoding="utf-8"))

        # Initialize seed fixtures if provided and exists
        if seed_file and seed_file.exists():
            conn.executescript(seed_file.read_text(encoding="utf-8"))

        return conn

    @classmethod
    def get_order(cls, conn: sqlite3.Connection, order_id: str) -> dict[str, Any] | None:
        """Convenience query: fetches an order as a plain dictionary, or None."""
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    @classmethod
    def get_audit_log(
        cls,
        conn: sqlite3.Connection,
        trial_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieves audit_log events recorded during a trial.
        Used by trajectory graders to inspect mutations and blocked invariant breaches.
        """
        cursor = conn.cursor()
        if trial_id:
            cursor.execute(
                "SELECT * FROM audit_log WHERE trial_id = ? ORDER BY log_id ASC",
                (trial_id,),
            )
        else:
            cursor.execute("SELECT * FROM audit_log ORDER BY log_id ASC")
        return [dict(row) for row in cursor.fetchall()]
