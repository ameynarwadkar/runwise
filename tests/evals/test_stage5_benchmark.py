"""
Unit tests for Stage 5 benchmark scenarios and evaluation runner.
"""

from runwise.evals.stage5_benchmark import (
    generate_stage5_benchmark_scenarios,
    export_stage5_holdout_file,
)
from runwise.evals.stage5_eval_runner import seed_stage5_fixtures
from runwise.domain.db import SandboxDB


def test_generate_stage5_benchmark_scenarios():
    scenarios = generate_stage5_benchmark_scenarios()
    assert len(scenarios) == 8, f"Expected 8 scenarios, got {len(scenarios)}"

    task_ids = [s.task_id for s in scenarios]
    assert len(task_ids) == len(set(task_ids)), "Duplicate task IDs found"

    # Verify all entities are in CUST-800 and ORD-900 quarantine ranges
    for s in scenarios:
        assert s.scenario.customer_id.startswith("CUST-80")
        assert s.split == "test"
        assert s.family_id.startswith("fam_stage5_")


def test_seed_stage5_fixtures():
    conn = SandboxDB.create_connection()
    seed_stage5_fixtures(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users WHERE user_id LIKE 'CUST-8%'")
    user_count = cursor.fetchone()[0]
    assert user_count == 8

    cursor.execute("SELECT COUNT(*) FROM orders WHERE order_id LIKE 'ORD-9%'")
    order_count = cursor.fetchone()[0]
    assert order_count >= 13

    cursor.execute("SELECT COUNT(*) FROM refunds WHERE order_id = 'ORD-906'")
    refund_count = cursor.fetchone()[0]
    assert refund_count == 2

    conn.close()
