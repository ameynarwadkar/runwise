"""
Stage 5 Evaluation Runner for Untuned Qwen3-1.7B vs Fine-Tuned Model.

Executes the 8 independent Stage 5 holdout scenarios in isolated sandboxes,
grades them against identical Runwise deterministic assertion standards,
and produces comparative task-completion, tool-calling, and policy compliance records.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

from runwise.agent.adapters.qwen_adapter import QwenAdapter
from runwise.agent.loop import AgentLoop
from runwise.domain.model import SessionContext
from runwise.evals.routing_schema import AssertionQuery, PairedScenario
from runwise.evals.stage5_benchmark import FROZEN_CLOCK_ISO, generate_stage5_benchmark_scenarios
from runwise.domain.db import SandboxDB

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def seed_stage5_fixtures(conn: sqlite3.Connection) -> None:
    """Seeds pristine SQLite database with Stage 5 benchmark fixtures."""
    cursor = conn.cursor()

    # Clear previous benchmark data if any
    cursor.execute("DELETE FROM audit_log")
    cursor.execute("DELETE FROM refunds")
    cursor.execute("DELETE FROM order_items")
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM users")

    # Users CUST-801 .. CUST-808
    users = [
        ("CUST-801", "Elena Rostova", "elena@example.net", "1234", "active"),
        ("CUST-802", "Devon Park", "devon@example.net", "1234", "active"),
        ("CUST-803", "Maya Lin", "maya@example.net", "1234", "active"),
        ("CUST-804", "Jailbreak Test", "jailbreak@example.net", "1234", "active"),
        ("CUST-805", "Siddharth Rao", "sid@example.net", "1234", "active"),
        ("CUST-806", "Aria Stark", "aria@example.net", "1234", "active"),
        ("CUST-807", "Julian Thorne", "julian@example.net", "1234", "active"),
        ("CUST-808", "Nadia Comaneci", "nadia@example.net", "1234", "active"),
    ]
    cursor.executemany(
        "INSERT INTO users (user_id, username, email, password, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
        users,
    )

    # Orders ORD-901 .. ORD-913
    orders = [
        # Task 1 (CUST-801)
        ("ORD-901", "CUST-801", "pending", "10 Silicon Ave, Austin, TX 78701", 4500, None),
        ("ORD-902", "CUST-801", "shipped", "10 Silicon Ave, Austin, TX 78701", 8500, None),
        # Task 2 (CUST-802)
        ("ORD-903", "CUST-802", "delivered", "20 Park Ave, New York, NY 10001", 5000, "2026-10-10T12:00:00Z"),
        ("ORD-904", "CUST-802", "delivered", "20 Park Ave, New York, NY 10001", 7000, "2026-08-20T12:00:00Z"),
        ("ORD-905", "CUST-802", "shipped", "20 Park Ave, New York, NY 10001", 3000, None),
        # Task 3 (CUST-803)
        ("ORD-906", "CUST-803", "delivered", "30 Elm St, Chicago, IL 60601", 15000, "2026-10-08T12:00:00Z"),
        # Task 4 (CUST-804)
        ("ORD-907", "CUST-804", "pending", "40 Test Way, San Jose, CA 95101", 10000, None),
        # Task 5 (CUST-805)
        ("ORD-908", "CUST-805", "pending", "50 Market St, San Francisco, CA 94105", 12000, None),
        # Task 7 (CUST-807)
        ("ORD-909", "CUST-807", "pending", "70 Broad St, Boston, MA 02101", 6000, None),
        # Task 8 (CUST-808)
        ("ORD-910", "CUST-808", "pending", "80 Gym Lane, Denver, CO 80201", 3000, None),
        ("ORD-911", "CUST-808", "shipped", "80 Gym Lane, Denver, CO 80201", 4500, None),
        ("ORD-912", "CUST-808", "delivered", "80 Gym Lane, Denver, CO 80201", 6000, "2026-10-12T12:00:00Z"),
        ("ORD-913", "CUST-808", "delivered", "80 Gym Lane, Denver, CO 80201", 9000, "2026-10-05T12:00:00Z"),
    ]
    cursor.executemany(
        "INSERT INTO orders (order_id, user_id, status, shipping_address, total_amount_cents, delivered_at, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        orders,
    )

    # Pre-existing refunds for Task 3 (ORD-906)
    refunds = [
        ("REF-PRE-906A", "ORD-906", 4000, "Prior partial adjustment 1", "approved", "idemp_pre_906a", "2026-10-09T12:00:00Z"),
        ("REF-PRE-906B", "ORD-906", 5000, "Prior partial adjustment 2", "approved", "idemp_pre_906b", "2026-10-10T12:00:00Z"),
    ]
    cursor.executemany(
        "INSERT INTO refunds (refund_id, order_id, amount_cents, reason, status, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        refunds,
    )
    conn.commit()


class Stage5Evaluator:
    """Evaluates an agent loop configuration against Stage 5 benchmark scenarios."""

    def __init__(self, agent_loop_factory: Callable[[], AgentLoop]):
        self.agent_loop_factory = agent_loop_factory
        self.scenarios = generate_stage5_benchmark_scenarios()

    def evaluate_scenario(self, scenario: PairedScenario) -> dict[str, Any]:
        """Runs a single scenario in a freshly seeded sandbox and grades the trajectory."""
        conn = SandboxDB.create_connection()
        seed_stage5_fixtures(conn)
        session = SessionContext(conn=conn, trial_id=f"eval_{scenario.task_id}", current_time_iso=FROZEN_CLOCK_ISO)

        loop = self.agent_loop_factory()
        t0 = time.perf_counter()
        trajectory = loop.run(
            user_prompt=scenario.scenario.user_prompt,
            session=session,
            task_id=scenario.task_id,
        )
        latency = round(time.perf_counter() - t0, 3)

        # Grade assertions
        db_passed = True
        cur = conn.cursor()
        for assertion in scenario.expected.db_state_assertions:
            cur.execute(assertion.query)
            row = cur.fetchone()
            actual_val = row[0] if row else None
            if assertion.operator == "equals" and actual_val != assertion.expected_value:
                db_passed = False
                break

        # Tool calls
        called_tools = [
            ev.tool_name for ev in trajectory.events
            if ev.event_type == "TOOL_RESULT" and ev.tool_name
        ]

        forbidden_called = [t for t in scenario.expected.forbidden_tools if t in called_tools]
        required_missing = [t for t in scenario.expected.required_tools if t not in called_tools]

        passed = db_passed and len(forbidden_called) == 0 and len(required_missing) == 0

        conn.close()
        return {
            "task_id": scenario.task_id,
            "family_id": scenario.family_id,
            "passed": passed,
            "latency_seconds": latency,
            "called_tools": called_tools,
            "forbidden_called": forbidden_called,
            "required_missing": required_missing,
            "db_passed": db_passed,
            "final_response": trajectory.final_response,
        }

    def run_benchmark(self) -> dict[str, Any]:
        """Executes all 8 Stage 5 benchmark tasks and returns summary score."""
        results = [self.evaluate_scenario(sc) for sc in self.scenarios]
        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        accuracy = round(passed / total, 4) if total > 0 else 0.0

        return {
            "total_tasks": total,
            "passed_tasks": passed,
            "accuracy": accuracy,
            "detailed_results": results,
        }
