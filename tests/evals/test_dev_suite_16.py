"""
Unit tests verifying Dev-Suite-16 isolation, fixture seeding, and deterministic graders.
"""

import sqlite3
import pytest
from runwise.domain.db import SandboxDB
from runwise.evals.dev_suite_16 import DEV_SCENARIOS, seed_dev_suite_16_db
from runwise.training.validator import QUARANTINED_ENTITIES

def test_dev_suite_16_length_and_domains():
    assert len(DEV_SCENARIOS) == 16
    domains = set(s.domain for s in DEV_SCENARIOS)
    assert len(domains) == 10  # All 10 domains represented

def test_dev_suite_16_zero_quarantine_overlap():
    for s in DEV_SCENARIOS:
        if s.customer_id:
            assert s.customer_id not in QUARANTINED_ENTITIES, f"Collision: {s.customer_id}"
            # Also ensure customer_id is not in candidate training range CUST-100..CUST-499
            cid_num = int(s.customer_id.split("-")[1])
            assert cid_num >= 700, f"Customer ID {s.customer_id} in training range!"
        if s.order_id:
            assert s.order_id not in QUARANTINED_ENTITIES, f"Collision: {s.order_id}"
            oid_num = int(s.order_id.replace("ORD-", "").replace("A", "").replace("B", ""))
            assert oid_num >= 800, f"Order ID {s.order_id} in training range!"

def test_dev_suite_16_seeding():
    conn = SandboxDB.create_connection()
    seed_dev_suite_16_db(conn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE user_id LIKE 'CUST-7%'")
    user_count = cur.fetchone()[0]
    assert user_count == 16

    cur.execute("SELECT COUNT(*) FROM orders WHERE order_id LIKE 'ORD-8%'")
    order_count = cur.fetchone()[0]
    assert order_count >= 14
    conn.close()
