"""
Session management and state persistence for the Runwise HTTP service.

Provides thread-safe lifecycle management for isolated customer support
sessions, mapping session IDs to active SessionContext instances and
ephemeral SQLite sandboxes.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext


@dataclass
class SessionEntry:
    """Internal container tracking a session's state and access timeline."""

    session_id: str
    context: SessionContext
    created_at: float
    last_accessed_at: float


class SessionManager:
    """
    Manages active customer support sessions with isolated sandboxes.

    Features:
    - Thread-safe session creation and access.
    - Automatic TTL-based inactivity expiration.
    - Bounded session memory via LRU eviction when max_sessions is reached.
    - Explicit resource cleanup closing underlying SQLite connections.
    """

    def __init__(self, ttl_seconds: float = 1800.0, max_sessions: int = 1000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[str, SessionEntry] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        session_id: str,
        customer_id: str | None = None,
        current_time_iso: str | None = None,
    ) -> SessionContext:
        """
        Retrieves an existing active session or initializes a fresh isolated sandbox.

        Parameters:
        -----------
        session_id: Unique identifier for the conversation session.
        customer_id: Optional pre-authenticated customer ID to attach.
        current_time_iso: Optional ISO timestamp override for deterministic testing.
        """
        now = time.time()
        with self._lock:
            # 1. Check if session already exists
            entry = self._sessions.get(session_id)
            if entry is not None:
                # Check if session has expired
                if now - entry.last_accessed_at > self.ttl_seconds:
                    self._close_entry(entry)
                    del self._sessions[session_id]
                else:
                    # Update access time
                    entry.last_accessed_at = now
                    # Attach customer_id if not yet authenticated
                    if customer_id and entry.context.authenticated_user_id is None:
                        entry.context.authenticated_user_id = customer_id
                    return entry.context

            # 2. Enforce max_sessions limit before allocating a new one
            if len(self._sessions) >= self.max_sessions:
                self._evict_oldest_session()

            # 3. Initialize fresh sandbox database connection
            conn = SandboxDB.create_connection()
            iso_now = current_time_iso or datetime.now(timezone.utc).isoformat()

            context = SessionContext(
                conn=conn,
                trial_id=session_id,
                current_time_iso=iso_now,
                authenticated_user_id=customer_id,
            )

            self._sessions[session_id] = SessionEntry(
                session_id=session_id,
                context=context,
                created_at=now,
                last_accessed_at=now,
            )
            return context

    def get(self, session_id: str) -> SessionContext | None:
        """
        Retrieves an active session without creating a new one if missing or expired.
        """
        now = time.time()
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                return None
            if now - entry.last_accessed_at > self.ttl_seconds:
                self._close_entry(entry)
                del self._sessions[session_id]
                return None

            entry.last_accessed_at = now
            return entry.context

    def close_session(self, session_id: str) -> bool:
        """
        Explicitly terminates a session, closing its database connection.
        Returns True if a session was found and closed, False otherwise.
        """
        with self._lock:
            entry = self._sessions.pop(session_id, None)
            if entry is not None:
                self._close_entry(entry)
                return True
            return False

    def cleanup_expired(self, now: float | None = None) -> int:
        """
        Scans all sessions and evicts any exceeding ttl_seconds of inactivity.
        Returns the number of evicted sessions.
        """
        current_time = now if now is not None else time.time()
        evicted_count = 0
        with self._lock:
            expired_ids = [
                sid
                for sid, entry in self._sessions.items()
                if current_time - entry.last_accessed_at > self.ttl_seconds
            ]
            for sid in expired_ids:
                entry = self._sessions.pop(sid)
                self._close_entry(entry)
                evicted_count += 1
        return evicted_count

    def active_session_count(self) -> int:
        """Returns the number of currently active sessions in memory."""
        with self._lock:
            return len(self._sessions)

    def clear(self) -> None:
        """Closes all active sessions and releases all database connections."""
        with self._lock:
            for entry in self._sessions.values():
                self._close_entry(entry)
            self._sessions.clear()

    def _evict_oldest_session(self) -> None:
        """Evicts the least recently accessed session to prevent unbounded memory growth."""
        if not self._sessions:
            return
        oldest_sid = min(self._sessions.keys(), key=lambda sid: self._sessions[sid].last_accessed_at)
        entry = self._sessions.pop(oldest_sid)
        self._close_entry(entry)

    @staticmethod
    def _close_entry(entry: SessionEntry) -> None:
        """Safely closes the underlying SQLite connection."""
        try:
            entry.context.conn.close()
        except Exception:
            pass
