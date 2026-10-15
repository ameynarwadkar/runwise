import sqlite3
from pathlib import Path 
import pytest

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "runwise" / "domain" / "schema.sql" 

def get_db_connection() -> sqlite3.Connection:
    """Creates a fresh in-memory database and initializes the schema."""
    conn = sqlite3.connect(':memory:')
    # Ensure foreign keys are enabled on every connection
    conn.execute("PRAGMA foreign_keys = ON;")
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    return conn

def test_schema_initialization():
    """Verify that all expected tables are created."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    
    expected_tables = {"users", "orders", "order_items", "refunds", "audit_log"}
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

def test_foreign_key_enforcement():
    """Verify foreign keys block orphan records."""
    conn = get_db_connection()
    # Inserting an order for a non-existent user must raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO orders (order_id, user_id, status, shipping_address, total_amount_cents, created_at)
            VALUES ('ORD-001', 'NONEXISTENT_USER', 'pending', '123 Main St', 5000, '2026-10-15T10:00:00Z');
            """
        )

def test_negative_refund_amount_blocked():
    """Verify check constraint blocks negative refund amounts."""
    conn = get_db_connection()
    # Seed parent user and order
    conn.execute("INSERT INTO users (user_id, username, email, password, status) VALUES ('U1', 'test', 'test@test.com', 'pass', 'active');")
    conn.execute("INSERT INTO orders (order_id, user_id, status, shipping_address, total_amount_cents, created_at) VALUES ('O1', 'U1', 'pending', '123 St', 5000, '2026-10-15T10:00:00Z');")
    conn.commit()
    # Attempt negative amount_cents
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO refunds (refund_id, order_id, amount_cents, reason, status, idempotency_key, created_at)
            VALUES ('REF-1', 'O1', -100, 'wrong item', 'approved', 'key-1', '2026-10-15T10:00:00Z');
            """
        )
    
def test_invalid_order_status_blocked():
    """Verify check constraint blocks invalid order status."""
    conn = get_db_connection()
    conn.execute("INSERT INTO users (user_id, username, email, password, status) VALUES ('U1', 'test', 'test@test.com', 'pass', 'active');")
    conn.commit()
    # 'in_transit' is not in ('pending', 'shipped', 'delivered', 'cancelled')
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO orders (order_id, user_id, status, shipping_address, total_amount_cents, created_at)
            VALUES ('O1', 'U1', 'in_transit', '123 St', 5000, '2026-10-15T10:00:00Z');
            """
        )

def test_duplicate_idempotency_key_blocked():
    """Verify idempotency_key uniqueness in refunds."""
    conn = get_db_connection()
    conn.execute("INSERT INTO users (user_id, username, email, password, status) VALUES ('U1', 'test', 'test@test.com', 'pass', 'active');")
    conn.execute("INSERT INTO orders (order_id, user_id, status, shipping_address, total_amount_cents, created_at) VALUES ('O1', 'U1', 'pending', '123 St', 5000, '2026-10-15T10:00:00Z');")
    
    # First refund succeeds
    conn.execute("INSERT INTO refunds (refund_id, order_id, amount_cents, reason, status, idempotency_key, created_at) VALUES ('REF-1', 'O1', 1000, 'reason', 'approved', 'key-dup', '2026-10-15T10:00:00Z');")
    conn.commit()
    # Second refund with same idempotency_key must raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO refunds (refund_id, order_id, amount_cents, reason, status, idempotency_key, created_at) VALUES ('REF-2', 'O1', 1000, 'reason', 'approved', 'key-dup', '2026-10-15T10:00:00Z');")