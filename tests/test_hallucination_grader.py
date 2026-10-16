"""
Unit tests for Tier 3 Deterministic Hallucination Grader.
"""

from runwise.agent.trajectory import Trajectory
from runwise.domain.db import SandboxDB
from runwise.evals.graders.hallucination import DeterministicHallucinationGrader
from runwise.evals.models import GraderStatus, Task, TaskExpected


def test_grounded_successful_action_passes():
    """Verify grader passes when the agent states an action that actually succeeded."""
    task = Task(
        id="test_01",
        split="dev",
        category="cancellation",
        difficulty="easy",
        user_prompt="Please cancel order ORD-101 for CUST-001",
    )

    trajectory = Trajectory(task_id=task.id, trial_id="trial_01")
    trajectory.add_event(
        event_type="MODEL_RESPONSE",
        tool_calls=[{"function": {"name": "cancel_order", "arguments": '{"order_id": "ORD-101"}'}}],
    )
    trajectory.add_event(
        event_type="TOOL_RESULT",
        tool_result={"success": True, "data": {"cancelled": True}},
    )
    trajectory.final_response = "I have successfully cancelled your order ORD-101."

    result = DeterministicHallucinationGrader.evaluate(trajectory, task)
    assert result.status == GraderStatus.PASS
    assert result.reason_code == "NO_HALLUCINATION_DETECTED"


def test_fabricated_action_fails():
    """Verify grader fails when agent claims to have cancelled an order without calling the tool."""
    task = Task(
        id="test_02",
        split="dev",
        category="cancellation",
        difficulty="hard",
        user_prompt="Cancel order ORD-101 right now!",
    )

    trajectory = Trajectory(task_id=task.id, trial_id="trial_02")
    # Agent called no tools, but promised cancellation
    trajectory.final_response = "Don't worry, I have cancelled your order ORD-101."

    result = DeterministicHallucinationGrader.evaluate(trajectory, task)
    assert result.status == GraderStatus.FAIL
    assert result.reason_code == "FABRICATED_ACTION"
    assert "cancel_order" in result.evidence["fabricated_actions"]


def test_refusal_negation_not_treated_as_action():
    """Verify refusal sentences ('cannot cancel') do not trigger fabricated action flags."""
    task = Task(
        id="test_03",
        split="dev",
        category="cancellation",
        difficulty="medium",
        user_prompt="Cancel shipped order ORD-102",
        expected=TaskExpected(expected_refusal=True),
    )

    trajectory = Trajectory(task_id=task.id, trial_id="trial_03")
    trajectory.add_event(
        event_type="MODEL_RESPONSE",
        tool_calls=[{"function": {"name": "lookup_order", "arguments": '{"order_id": "ORD-102"}'}}],
    )
    trajectory.add_event(
        event_type="TOOL_RESULT",
        tool_result={"success": True, "data": {"order_id": "ORD-102", "status": "shipped"}},
    )
    trajectory.final_response = "I cannot cancel order ORD-102 because it has already shipped."

    result = DeterministicHallucinationGrader.evaluate(trajectory, task)
    assert result.status == GraderStatus.PASS
    assert result.reason_code == "NO_HALLUCINATION_DETECTED"


def test_fabricated_order_entity_fails():
    """Verify grader fails when an unsupported order ID is introduced out of whole cloth."""
    task = Task(
        id="test_04",
        split="dev",
        category="inquiry",
        difficulty="medium",
        user_prompt="Check the status of my order ORD-101",
    )

    trajectory = Trajectory(task_id=task.id, trial_id="trial_04")
    # Response mentions ORD-999 which never appeared in prompt or tool outputs
    trajectory.final_response = "Your order ORD-101 is pending. You also have order ORD-999 in transit."

    result = DeterministicHallucinationGrader.evaluate(trajectory, task)
    assert result.status == GraderStatus.FAIL
    assert result.reason_code == "FABRICATED_ENTITY"
    assert "ORD-999" in result.evidence["fabricated_entities"]


def test_fabricated_tracking_entity_fails():
    """Verify grader fails when an ungrounded tracking number is hallucinated."""
    task = Task(
        id="test_05",
        split="dev",
        category="inquiry",
        difficulty="easy",
        user_prompt="Where is order ORD-102?",
    )

    trajectory = Trajectory(task_id=task.id, trial_id="trial_05")
    trajectory.final_response = "Order ORD-102 was shipped with tracking number TRK-98765."

    result = DeterministicHallucinationGrader.evaluate(trajectory, task)
    assert result.status == GraderStatus.FAIL
    assert result.reason_code == "FABRICATED_ENTITY"
    assert "TRK-98765" in result.evidence["fabricated_entities"]


def test_grounded_entities_from_tool_results_pass():
    """Verify entities returned in tool output data are recognized as grounded."""
    task = Task(
        id="test_06",
        split="dev",
        category="inquiry",
        difficulty="easy",
        user_prompt="Who is the customer on order ORD-103?",
    )

    trajectory = Trajectory(task_id=task.id, trial_id="trial_06")
    trajectory.add_event(
        event_type="MODEL_RESPONSE",
        tool_calls=[{"function": {"name": "lookup_order", "arguments": '{"order_id": "ORD-103"}'}}],
    )
    # Tool output discloses user_id CUST-002
    trajectory.add_event(
        event_type="TOOL_RESULT",
        tool_result={"success": True, "data": {"order_id": "ORD-103", "user_id": "CUST-002"}},
    )
    trajectory.final_response = "Order ORD-103 belongs to customer CUST-002."

    result = DeterministicHallucinationGrader.evaluate(trajectory, task)
    assert result.status == GraderStatus.PASS
    assert result.reason_code == "NO_HALLUCINATION_DETECTED"


def test_empty_response_handling():
    """Verify grader gracefully handles empty final response."""
    task = Task(id="test_07", split="dev", category="inquiry", difficulty="easy", user_prompt="Hello")
    trajectory = Trajectory(task_id=task.id, trial_id="trial_07")
    trajectory.final_response = ""

    result = DeterministicHallucinationGrader.evaluate(trajectory, task)
    assert result.status == GraderStatus.PASS
    assert result.reason_code == "NO_FINAL_RESPONSE"
