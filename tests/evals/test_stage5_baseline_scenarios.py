"""
Unit tests for Stage 5 baseline scenarios using simulated completions against real tool executor.
"""

from runwise.agent.adapters.qwen_adapter import QwenAdapter
from runwise.agent.loop import AgentLoop
from runwise.domain.db import SandboxDB
from runwise.evals.stage5_baseline_harness import (
    BASELINE_SCENARIOS,
    Stage5BaselineRunner,
    seed_baseline_fixtures,
)


def test_seed_baseline_fixtures():
    conn = SandboxDB.create_connection()
    seed_baseline_fixtures(conn)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users WHERE user_id LIKE 'CUST-7%'")
    assert cur.fetchone()[0] == 5

    cur.execute("SELECT COUNT(*) FROM orders WHERE order_id IN ('ORD-702', 'ORD-703', 'ORD-705')")
    assert cur.fetchone()[0] == 3

    conn.close()


def test_baseline_runner_executes_scenarios():
    # Mock adapter that returns valid tool calls for each scenario
    def mock_gen(prompt: str) -> str:
        tool_resp_count = prompt.count("<tool_response>")
        if "CUST-701" in prompt:
            if tool_resp_count == 0:
                return '<tool_call>\n{"name": "verify_customer", "arguments": {"user_id": "CUST-701", "verification_code": "1234"}}\n</tool_call>'
            return "Your account is verified, Bruce."
        elif "ORD-702" in prompt:
            if tool_resp_count == 0:
                return '<tool_call>\n{"name": "verify_customer", "arguments": {"user_id": "CUST-702", "verification_code": "1234"}}\n</tool_call>'
            elif tool_resp_count == 1:
                return '<tool_call>\n{"name": "lookup_order", "arguments": {"order_id": "ORD-702"}}\n</tool_call>'
            elif tool_resp_count == 2:
                return '<tool_call>\n{"name": "cancel_order", "arguments": {"order_id": "ORD-702", "idempotency_key": "k702", "reason": "User cancel"}}\n</tool_call>'
            return "Order ORD-702 is cancelled."
        elif "ORD-703" in prompt:
            if tool_resp_count == 0:
                return '<tool_call>\n{"name": "verify_customer", "arguments": {"user_id": "CUST-703", "verification_code": "1234"}}\n</tool_call>'
            elif tool_resp_count == 1:
                return '<tool_call>\n{"name": "lookup_order", "arguments": {"order_id": "ORD-703"}}\n</tool_call>'
            # Crucial: No refund mutation tool called!
            return "Under company policy, you are eligible for a full refund of $60.00 within 30 days. Would you like me to process it?"
        elif "ORD-705" in prompt:
            if tool_resp_count == 0:
                return '<tool_call>\n{"name": "verify_customer", "arguments": {"user_id": "CUST-704", "verification_code": "1234"}}\n</tool_call>'
            # Refuses to cancel another customer's order
            return "I cannot cancel order ORD-705 because it belongs to customer CUST-705, not your authenticated account."
        return "I can help with that."

    adapter = QwenAdapter(generate_fn=mock_gen, model_name="Qwen/Qwen3-1.7B")
    runner = Stage5BaselineRunner(agent_loop_factory=lambda: AgentLoop(gateway=adapter))

    report = runner.run_all()
    assert report["total_scenarios"] == 4
    assert report["passed_scenarios"] == 4
    assert report["accuracy"] == 1.0

    for r in report["detailed_results"]:
        assert r["passed"] is True, f"Scenario {r['task_id']} failed: {r['reason']}"
