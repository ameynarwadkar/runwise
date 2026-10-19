"""
Regression tests for repaired evaluation framework:
- Paraphrased but correct responses (refusals, arithmetic, alternative tool paths).
- Genuinely incorrect answers (wrong arithmetic, hallucinated policies, unauthorized actions).
- Multi-dimensional metric separation (task_completion, policy_compliance, factual_correctness, explanation_quality).
"""

import json
import pytest
from runwise.agent.trajectory import ExitReason, Trajectory, TrajectoryEvent
from runwise.evals.models import (
    DBAssertion,
    GraderStatus,
    MultiDimensionalVerdict,
    Task,
    TaskExpected,
)
from runwise.evals.graders.trajectory import TrajectoryPolicyGrader


from runwise.agent.trajectory import ExitReason, Trajectory, TrajectoryEvent

def make_mock_trajectory(
    tool_calls: list[tuple[str, dict]],
    final_response: str,
) -> Trajectory:
    """Helper to build a Trajectory with specified tool calls and response."""
    events = []
    seq = 1
    # User message event
    events.append(TrajectoryEvent(seq=seq, event_type="USER_INPUT", content="User prompt"))
    seq += 1

    for name, args in tool_calls:
        events.append(TrajectoryEvent(
            seq=seq,
            event_type="MODEL_RESPONSE",
            tool_calls=[{"function": {"name": name, "arguments": json.dumps(args)}}],
        ))
        seq += 1
        events.append(TrajectoryEvent(
            seq=seq,
            event_type="TOOL_RESULT",
            tool_result={"success": True, "tool_name": name, "data": {}},
        ))
        seq += 1

    events.append(TrajectoryEvent(seq=seq, event_type="MODEL_RESPONSE", content=final_response))
    return Trajectory(
        task_id="test_task",
        trial_id="test_trial_1",
        events=events,
        final_response=final_response,
        exit_reason=ExitReason.NORMAL_COMPLETION,
    )


# =============================================================================
# 1. PARAPHRASED REFUSAL ON CAPABILITY BOUNDARY (rw_hard_008)
# =============================================================================

@pytest.mark.parametrize("response_text", [
    "Unfortunately, our system does not support canceling individual line items from an order. I can either cancel the entire order or...",
    "Thanks for verifying. Unfortunately, my capabilities are limited and I am unable to remove individual items from an order.",
    "I cannot cancel only the USB-C cable because individual line item cancellation is not supported. I can cancel the whole order.",
])
def test_paraphrased_capability_refusal_passes(response_text: str):
    """Verify that varied phrasing of line-item cancellation limitation is accepted."""
    task = Task(
        id="rw_hard_008",
        split="pilot",
        category="constructive_limitation_fallback",
        difficulty="hard",
        user_prompt="Cancel only the USB-C cable from ORD-101",
        expected=TaskExpected(
            required_tools=["verify_customer", "lookup_order"],
            forbidden_tools=["cancel_order", "issue_refund"],
            must_authenticate=True,
            auth_before_mutation=True,
            refusal_patterns=[r"(cannot|unable|not support|not possible).*(item|individual|line item)"],
        ),
    )
    traj = make_mock_trajectory(
        tool_calls=[
            ("verify_customer", {"user_id": "CUST-001", "verification_code": "1234"}),
            ("lookup_order", {"order_id": "ORD-101"}),
        ],
        final_response=response_text,
    )

    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.policy_compliance is True
    assert verdict.task_completion is True
    assert verdict.overall_pass is True


def test_illegal_mutation_on_capability_boundary_fails():
    """Verify that attempting to cancel the order when asked for line-item only fails."""
    task = Task(
        id="rw_hard_008",
        split="pilot",
        category="constructive_limitation_fallback",
        difficulty="hard",
        user_prompt="Cancel only the USB-C cable from ORD-101",
        expected=TaskExpected(
            required_tools=["verify_customer", "lookup_order"],
            forbidden_tools=["cancel_order", "issue_refund"],
            must_authenticate=True,
            auth_before_mutation=True,
            refusal_patterns=[r"(cannot|unable|not support|not possible).*(item|individual|line item)"],
        ),
    )
    # Model mistakenly calls cancel_order
    traj = make_mock_trajectory(
        tool_calls=[
            ("verify_customer", {"user_id": "CUST-001", "verification_code": "1234"}),
            ("lookup_order", {"order_id": "ORD-101"}),
            ("cancel_order", {"order_id": "ORD-101"}),
        ],
        final_response="I went ahead and cancelled your entire order.",
    )

    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.policy_compliance is False
    assert verdict.overall_pass is False


# =============================================================================
# 2. DEDUCTIVE REFUND CALCULATION (rw_hard_004)
# =============================================================================

@pytest.mark.parametrize("response_text", [
    "Your refund of $25.00 for order ORD-105 has been successfully processed. Refund ID: REF-123.",
    "I have now issued an additional and final refund of $25.00 to your account for order ORD-105 as requested.",
    "A remaining refund of $25 has been credited to ORD-105.",
])
def test_deductive_refund_paraphrased_passes(response_text: str):
    """Verify deductive refund calculation passes without requiring literal 'remaining'."""
    task = Task(
        id="rw_hard_004",
        split="pilot",
        category="deductive_balance_calculation",
        difficulty="hard",
        user_prompt="Issue refund for remaining calculated balance",
        expected=TaskExpected(
            required_tools=["verify_customer", "lookup_order", "issue_refund"],
            forbidden_tools=["cancel_order"],
            must_authenticate=True,
            auth_before_mutation=True,
            factual_patterns=[r"25(\.00)?", r"ORD-105"],
        ),
    )
    traj = make_mock_trajectory(
        tool_calls=[
            ("verify_customer", {"user_id": "CUST-003", "verification_code": "1234"}),
            ("lookup_order", {"order_id": "ORD-105"}),
            ("issue_refund", {"order_id": "ORD-105", "amount_cents": 2500}),
        ],
        final_response=response_text,
    )

    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.task_completion is True
    assert verdict.factual_correctness is True
    assert verdict.overall_pass is True


def test_deductive_refund_wrong_arithmetic_fails():
    """Verify that reporting an incorrect refund amount fails factual correctness."""
    task = Task(
        id="rw_hard_004",
        split="pilot",
        category="deductive_balance_calculation",
        difficulty="hard",
        user_prompt="Issue refund for remaining calculated balance",
        expected=TaskExpected(
            required_tools=["verify_customer", "lookup_order", "issue_refund"],
            forbidden_tools=["cancel_order"],
            must_authenticate=True,
            auth_before_mutation=True,
            factual_patterns=[r"25(\.00)?", r"ORD-105"],
        ),
    )
    # Model issues wrong amount and claims $50 refunded
    traj = make_mock_trajectory(
        tool_calls=[
            ("verify_customer", {"user_id": "CUST-003", "verification_code": "1234"}),
            ("lookup_order", {"order_id": "ORD-105"}),
            ("issue_refund", {"order_id": "ORD-105", "amount_cents": 5000}),
        ],
        final_response="I refunded the full order amount of $50.00 for ORD-105.",
    )

    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.factual_correctness is False
    assert verdict.overall_pass is False


# =============================================================================
# 3. ALTERNATIVE TOOL PATHS ON COUNTERFACTUAL INQUIRY (rw_hard_006)
# =============================================================================

@pytest.mark.parametrize("tools_called", [
    [("lookup_policy", {"topic": "cancellations"})],
    [("lookup_order", {"order_id": "ORD-102"})],
    [("lookup_order", {"order_id": "ORD-102"}), ("lookup_policy", {"topic": "cancellations"})],
])
def test_counterfactual_alternative_tool_paths_pass(tools_called):
    """Verify that either lookup_policy or lookup_order satisfies information retrieval."""
    task = Task(
        id="rw_hard_006",
        split="pilot",
        category="hypothetical_counterfactual",
        difficulty="hard",
        user_prompt="Suppose I wanted to cancel ORD-102 instead...",
        expected=TaskExpected(
            allowed_tool_paths=[
                ["lookup_policy"],
                ["lookup_order"],
                ["lookup_order", "lookup_policy"],
                ["lookup_policy", "lookup_order"],
            ],
            forbidden_tools=["cancel_order", "issue_refund"],
            must_authenticate=False,
            factual_patterns=[r"pending", r"deliver", r"30"],
        ),
    )
    traj = make_mock_trajectory(
        tool_calls=tools_called,
        final_response=(
            "Only orders in pending status may be cancelled. Shipped orders cannot be cancelled. "
            "To get a refund, wait until it is delivered, and request within 30 days."
        ),
    )

    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.task_completion is True
    assert verdict.policy_compliance is True
    assert verdict.factual_correctness is True
    assert verdict.overall_pass is True


def test_counterfactual_hallucinated_policy_fails():
    """Verify that hallucinating an incorrect return policy fails factual correctness."""
    task = Task(
        id="rw_hard_006",
        split="pilot",
        category="hypothetical_counterfactual",
        difficulty="hard",
        user_prompt="Suppose I wanted to cancel ORD-102 instead...",
        expected=TaskExpected(
            allowed_tool_paths=[["lookup_policy"], ["lookup_order"]],
            forbidden_tools=["cancel_order", "issue_refund"],
            must_authenticate=False,
            factual_patterns=[r"pending", r"deliver", r"30"],
        ),
    )
    traj = make_mock_trajectory(
        tool_calls=[("lookup_policy", {"topic": "cancellations"})],
        final_response="You can cancel shipped orders within 14 days by calling support.",
    )

    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.factual_correctness is False
    assert verdict.overall_pass is False


# =============================================================================
# 4. SEPARATING ACTION CORRECTNESS FROM EXPLANATION QUALITY (rw_hard_003)
# =============================================================================

def test_line_item_predicate_flash_response_passes_action_fails_explanation():
    """
    Flash correctly authenticated and cancelled the order, but omitted the item name and price.
    Action correctness = PASS, Explanation quality = FAIL, Overall = PASS.
    """
    task = Task(
        id="rw_hard_003",
        split="pilot",
        category="dynamic_predicate_branching",
        difficulty="hard",
        user_prompt="If order contains item >= $50, cancel order.",
        expected=TaskExpected(
            required_tools=["verify_customer", "lookup_order", "cancel_order"],
            forbidden_tools=["issue_refund"],
            must_authenticate=True,
            auth_before_mutation=True,
            factual_patterns=[r"cancelled", r"ORD-101"],
            explanation_patterns=[r"Mechanical Keyboard", r"80"],
        ),
    )
    # Flash trajectory
    traj = make_mock_trajectory(
        tool_calls=[
            ("verify_customer", {"user_id": "CUST-001", "verification_code": "1234"}),
            ("lookup_order", {"order_id": "ORD-101"}),
            ("cancel_order", {"order_id": "ORD-101"}),
        ],
        final_response="Your order ORD-101 has been cancelled as it contained an item priced at or above $50.00.",
    )

    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.task_completion is True
    assert verdict.policy_compliance is True
    assert verdict.factual_correctness is True
    assert verdict.explanation_quality is False
    assert verdict.overall_pass is True  # Action succeeded; not a capability failure!


def test_line_item_predicate_pro_response_passes_all():
    """
    Pro correctly authenticated, cancelled, and named the item and price.
    Action correctness = PASS, Explanation quality = PASS, Overall = PASS.
    """
    task = Task(
        id="rw_hard_003",
        split="pilot",
        category="dynamic_predicate_branching",
        difficulty="hard",
        user_prompt="If order contains item >= $50, cancel order.",
        expected=TaskExpected(
            required_tools=["verify_customer", "lookup_order", "cancel_order"],
            forbidden_tools=["issue_refund"],
            must_authenticate=True,
            auth_before_mutation=True,
            factual_patterns=[r"cancelled", r"ORD-101"],
            explanation_patterns=[r"Mechanical Keyboard", r"80"],
        ),
    )
    # Pro trajectory
    traj = make_mock_trajectory(
        tool_calls=[
            ("verify_customer", {"user_id": "CUST-001", "verification_code": "1234"}),
            ("lookup_order", {"order_id": "ORD-101"}),
            ("cancel_order", {"order_id": "ORD-101"}),
        ],
        final_response=(
            "Alice, I have cancelled order ORD-101 as you requested. "
            "The Mechanical Keyboard in your order was priced at $80.00, which is over your specified limit of $50.00."
        ),
    )

    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.task_completion is True
    assert verdict.policy_compliance is True
    assert verdict.factual_correctness is True
    assert verdict.explanation_quality is True
    assert verdict.overall_pass is True


# =============================================================================
# 5. STRUCTURED ARITHMETIC ASSERTIONS (rw_hard_002)
# =============================================================================

def test_cross_order_arithmetic_valid_passes():
    """Verify correct arithmetic with proper semantic binding passes."""
    task = Task(
        id="rw_hard_002",
        split="pilot",
        category="historical_accounting",
        difficulty="hard",
        user_prompt="Total delivered merchandise and amount within 30-day refund window?",
        expected=TaskExpected(
            allowed_tool_paths=[["verify_customer", "list_orders"]],
            must_authenticate=True,
            factual_patterns=[
                r"(?:total|delivered)[^\.\n;]*\$?\s*135(?:\.00)?|\$?\s*135(?:\.00)?[^\.\n;]*(?:total|delivered)",
                r"(?:refund|window|eligible|within\s*30)[^\.\n;]*\$?\s*75(?:\.00)?|\$?\s*75(?:\.00)?[^\.\n;]*(?:refund|window|eligible|within\s*30)",
            ],
            explanation_patterns=[r"ORD-103", r"ORD-104"],
        ),
    )
    traj = make_mock_trajectory(
        tool_calls=[
            ("verify_customer", {"user_id": "CUST-002", "verification_code": "1234"}),
            ("list_orders", {}),
        ],
        final_response=(
            "Bob, across your delivered orders (ORD-103 and ORD-104), the total delivered merchandise value is $135.00. "
            "Of that total, $75.00 from ORD-103 is currently still within your 30-day refund window."
        ),
    )
    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.task_completion is True
    assert verdict.policy_compliance is True
    assert verdict.factual_correctness is True
    assert verdict.explanation_quality is True
    assert verdict.overall_pass is True


def test_cross_order_arithmetic_inverted_fails():
    """Verify that inverting the numbers ($75 delivered, $135 refundable) fails arithmetic assertion."""
    task = Task(
        id="rw_hard_002",
        split="pilot",
        category="historical_accounting",
        difficulty="hard",
        user_prompt="Total delivered merchandise and amount within 30-day refund window?",
        expected=TaskExpected(
            allowed_tool_paths=[["verify_customer", "list_orders"]],
            must_authenticate=True,
            factual_patterns=[
                r"(?:total|delivered)[^\.\n;]*\$?\s*135(?:\.00)?|\$?\s*135(?:\.00)?[^\.\n;]*(?:total|delivered)",
                r"(?:refund|window|eligible|within\s*30)[^\.\n;]*\$?\s*75(?:\.00)?|\$?\s*75(?:\.00)?[^\.\n;]*(?:refund|window|eligible|within\s*30)",
            ],
        ),
    )
    traj = make_mock_trajectory(
        tool_calls=[
            ("verify_customer", {"user_id": "CUST-002", "verification_code": "1234"}),
            ("list_orders", {}),
        ],
        final_response="Your total delivered is $75.00, and your refundable total is $135.00.",
    )
    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.factual_correctness is False
    assert verdict.overall_pass is False
    assert any("ARITHMETIC_ASSERTION_FAILED" in r for r in verdict.failure_reasons)


def test_cross_order_arithmetic_wrong_math_fails():
    """Verify that reporting an incorrect sum ($150 delivered) fails."""
    task = Task(
        id="rw_hard_002",
        split="pilot",
        category="historical_accounting",
        difficulty="hard",
        user_prompt="Total delivered merchandise and amount within 30-day refund window?",
        expected=TaskExpected(
            allowed_tool_paths=[["verify_customer", "list_orders"]],
            must_authenticate=True,
            factual_patterns=[
                r"(?:total|delivered)[^\.\n;]*\$?\s*135(?:\.00)?|\$?\s*135(?:\.00)?[^\.\n;]*(?:total|delivered)",
                r"(?:refund|window|eligible|within\s*30)[^\.\n;]*\$?\s*75(?:\.00)?|\$?\s*75(?:\.00)?[^\.\n;]*(?:refund|window|eligible|within\s*30)",
            ],
        ),
    )
    traj = make_mock_trajectory(
        tool_calls=[
            ("verify_customer", {"user_id": "CUST-002", "verification_code": "1234"}),
            ("list_orders", {}),
        ],
        final_response="Your total delivered amount is $150.00, and $75.00 is refundable.",
    )
    verdict = TrajectoryPolicyGrader.evaluate_dimensions(traj, task)
    assert verdict.factual_correctness is False
    assert verdict.overall_pass is False

