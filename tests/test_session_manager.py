"""
Unit tests for SessionManager: verifies isolated sandboxing, multi-turn state
persistence, TTL expiration, max capacity eviction, and resource cleanup.
"""

import sqlite3
import pytest

from runwise.service.session import SessionManager


def test_session_manager_creates_fresh_sandbox():
    """Verify that a new session gets an active SQLite sandbox populated with seed data."""
    manager = SessionManager()
    session = manager.get_or_create("sess_test_1")

    assert session.trial_id == "sess_test_1"
    assert session.authenticated_user_id is None

    # Verify seed table is populated and readable
    cursor = session.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders;")
    (count,) = cursor.fetchone()
    assert count > 0
    manager.clear()


def test_session_manager_persists_state_across_turns():
    """
    Verify that calling get_or_create with the same session_id returns the identical
    sandbox connection, preserving in-memory mutations.
    """
    manager = SessionManager()
    s1 = manager.get_or_create("sess_turn_1")

    # Turn 1: Modify database state in session (updating existing CUST-001)
    s1.conn.execute("UPDATE users SET username = 'alice_turn1' WHERE user_id = 'CUST-001';")
    s1.conn.commit()
    s1.authenticated_user_id = "CUST-001"

    # Turn 2: Request same session
    s2 = manager.get_or_create("sess_turn_1")
    assert s2 is s1
    assert s2.authenticated_user_id == "CUST-001"

    # Verify mutation is preserved
    cursor = s2.conn.cursor()
    cursor.execute("SELECT username FROM users WHERE user_id = 'CUST-001';")
    (username,) = cursor.fetchone()
    assert username == "alice_turn1"
    manager.clear()


def test_session_manager_isolation_between_sessions():
    """Verify two distinct sessions have completely isolated database sandboxes."""
    manager = SessionManager()
    s_a = manager.get_or_create("sess_a")
    s_b = manager.get_or_create("sess_b")

    s_a.conn.execute("UPDATE users SET username = 'alice_in_a' WHERE user_id = 'CUST-001';")
    s_a.conn.commit()

    cursor_b = s_b.conn.cursor()
    cursor_b.execute("SELECT username FROM users WHERE user_id = 'CUST-001';")
    (username_b,) = cursor_b.fetchone()
    assert username_b != "alice_in_a"
    manager.clear()


def test_session_manager_close_session_releases_db():
    """Verify closing a session removes it and closes the SQLite connection."""
    manager = SessionManager()
    session = manager.get_or_create("sess_to_close")
    conn = session.conn

    assert manager.active_session_count() == 1
    closed = manager.close_session("sess_to_close")
    assert closed is True
    assert manager.active_session_count() == 0

    # Attempting to use a closed SQLite connection raises ProgrammingError
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1;")


def test_session_manager_ttl_expiration():
    """Verify expired sessions are cleaned up based on inactivity TTL."""
    # Set short TTL of 1.0 second
    manager = SessionManager(ttl_seconds=1.0)
    manager.get_or_create("sess_expired")

    assert manager.active_session_count() == 1

    # Simulate 2 seconds passing
    future_time = manager._sessions["sess_expired"].last_accessed_at + 2.0
    evicted = manager.cleanup_expired(now=future_time)

    assert evicted == 1
    assert manager.active_session_count() == 0
    assert manager.get("sess_expired") is None


def test_session_manager_max_sessions_eviction():
    """Verify reaching max_sessions evicts the oldest inactive session."""
    manager = SessionManager(max_sessions=2)
    s1 = manager.get_or_create("sess_1")
    # Manually adjust access time to make sess_1 definitely older
    manager._sessions["sess_1"].last_accessed_at -= 10.0

    s2 = manager.get_or_create("sess_2")
    assert manager.active_session_count() == 2

    # Creating a 3rd session should evict sess_1
    s3 = manager.get_or_create("sess_3")
    assert manager.active_session_count() == 2
    assert manager.get("sess_1") is None
    assert manager.get("sess_2") is not None
    assert manager.get("sess_3") is not None
    manager.clear()
