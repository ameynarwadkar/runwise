"""
Validates trial sandbox isolation, seed loading, and audit log extraction.
"""

from runwise.domain.db import SandboxDB


def test_base_seed_loading():
    """Verify that the base seed populates customers, orders, and refund history."""
    conn = SandboxDB.create_connection()

    # Check customer
    cursor = conn.cursor()
    cursor.execute("SELECT email, status FROM users WHERE user_id = 'CUST-001'")
    user = cursor.fetchone()
    assert user is not None
    assert user["email"] == "alice@example.com"
    assert user["status"] == "active"

    # Check order
    order = SandboxDB.get_order(conn, "ORD-101")
    assert order is not None
    assert order["status"] == "pending"
    assert order["total_amount_cents"] == 10000

    # Check existing partial refund
    cursor.execute("SELECT amount_cents, status FROM refunds WHERE refund_id = 'REF-001'")
    refund = cursor.fetchone()
    assert refund is not None
    assert refund["amount_cents"] == 2500
    assert refund["status"] == "approved"


def test_trial_isolation():
    """
    CRITICAL RELIABILITY TEST:
    Prove that two trials running concurrently start with the same data,
    and a mutation in Trial A does NOT affect Trial B.
    """
    # Simulate Trial A and Trial B starting concurrently
    conn_trial_a = SandboxDB.create_connection()
    conn_trial_b = SandboxDB.create_connection()

    # Both see ORD-101 as pending initially
    assert SandboxDB.get_order(conn_trial_a, "ORD-101")["status"] == "pending"
    assert SandboxDB.get_order(conn_trial_b, "ORD-101")["status"] == "pending"

    # Trial A cancels ORD-101
    conn_trial_a.execute(
        "UPDATE orders SET status = 'cancelled' WHERE order_id = 'ORD-101';"
    )
    conn_trial_a.commit()

    # Verify Trial A sees the mutation
    assert SandboxDB.get_order(conn_trial_a, "ORD-101")["status"] == "cancelled"

    # Verify Trial B is COMPLETELY ISOLATED and still sees 'pending'
    order_b = SandboxDB.get_order(conn_trial_b, "ORD-101")
    assert order_b["status"] == "pending", (
        f"Isolation breach! Trial B saw Trial A's mutation: {order_b['status']}"
    )


def test_audit_log_capture():
    """Verify audit log events are recorded and retrievable per trial_id."""
    conn = SandboxDB.create_connection()

    # Record a simulated mutation event in the audit log
    conn.execute(
        """
        INSERT INTO audit_log (
            trial_id, event_type, tool_name, user_id, order_id, 
            idempotency_key, status_code, details_json, timestamp
        ) VALUES (
            'trial_test_99', 'MUTATION_EXECUTED', 'cancel_order', 'CUST-001', 'ORD-101',
            'idemp_abc_1', 'SUCCESS', '{"reason": "customer requested"}', 1700000000
        );
        """
    )
    conn.commit()

    # Fetch audit log for this trial
    logs = SandboxDB.get_audit_log(conn, trial_id="trial_test_99")
    assert len(logs) == 1
    assert logs[0]["tool_name"] == "cancel_order"
    assert logs[0]["event_type"] == "MUTATION_EXECUTED"

    # Fetching for another trial_id yields empty
    other_logs = SandboxDB.get_audit_log(conn, trial_id="trial_other_00")
    assert len(other_logs) == 0
