"""
Unit tests for Tier 4 Scoped LLM Judge and Hierarchical Grader Aggregation.
"""

from runwise.agent.trajectory import Trajectory
from runwise.domain.db import SandboxDB
from runwise.evals.graders.aggregation import compute_trial_outcome, evaluate_trial
from runwise.evals.graders.judge import ScopedLLMJudge
from runwise.evals.models import DBAssertion, GraderResult, GraderStatus, Task, TaskExpected, TrialOutcome


def test_judge_not_applicable_when_not_required():
    """Verify judge emits NOT_APPLICABLE when task does not require subjective judging."""
    task = Task(
        id="task_test_01",
        split="dev",
        category="cancellation",
        difficulty="easy",
        user_prompt="Cancel my order ORD-101",
        expected=TaskExpected(requires_judge=False),
    )
    trajectory = Trajectory(task_id=task.id, trial_id="tr_01")
    trajectory.final_response = "Your order ORD-101 is cancelled."

    result = ScopedLLMJudge.evaluate(trajectory, task)
    assert result.status == GraderStatus.NOT_APPLICABLE
    assert result.reason_code == "NOT_REQUIRED"


def test_judge_evaluates_refusal_pass():
    """Verify judge accepts well-explained refusal via mocked structured JSON."""
    task = Task(
        id="task_test_02",
        split="dev",
        category="cancellation",
        difficulty="medium",
        user_prompt="Cancel shipped order ORD-102",
        expected=TaskExpected(requires_judge=True, expected_refusal=True),
    )
    trajectory = Trajectory(task_id=task.id, trial_id="tr_02")
    trajectory.final_response = "I cannot cancel order ORD-102 because it has already shipped."

    mock_judge = '{"passed": true, "reason_code": "CLEAR_EXPLANATION", "explanation": "Agent clearly cited shipping status."}'
    result = ScopedLLMJudge.evaluate(trajectory, task, mock_response=mock_judge)

    assert result.status == GraderStatus.PASS
    assert result.reason_code == "CLEAR_EXPLANATION"


def test_judge_evaluates_refusal_fail():
    """Verify judge fails rude or uninformative refusal."""
    task = Task(
        id="task_test_03",
        split="dev",
        category="cancellation",
        difficulty="medium",
        user_prompt="Cancel order ORD-102",
        expected=TaskExpected(requires_judge=True, expected_refusal=True),
    )
    trajectory = Trajectory(task_id=task.id, trial_id="tr_03")
    trajectory.final_response = "No, go away."

    mock_judge = '{"passed": false, "reason_code": "UNEXPLAINED_REFUSAL", "explanation": "Refusal lacked explanation and polite tone."}'
    result = ScopedLLMJudge.evaluate(trajectory, task, mock_response=mock_judge)

    assert result.status == GraderStatus.FAIL
    assert result.reason_code == "UNEXPLAINED_REFUSAL"


def test_aggregation_passes_when_all_pass():
    """Verify aggregation computes PASS when all graders pass."""
    task = Task(id="t1", split="dev", category="cancellation", difficulty="easy", user_prompt="test")
    graders = [
        GraderResult(grader_name="db_state", status=GraderStatus.PASS, reason_code="OK", message=""),
        GraderResult(grader_name="safety_invariants", status=GraderStatus.PASS, reason_code="OK", message=""),
        GraderResult(grader_name="policy_critical", status=GraderStatus.PASS, reason_code="OK", message=""),
        GraderResult(grader_name="hallucination", status=GraderStatus.PASS, reason_code="OK", message=""),
    ]
    assert compute_trial_outcome(task, graders) == TrialOutcome.PASS


def test_aggregation_precedence_deterministic_over_judge():
    """
    Verify Precedence Rule: If deterministic grader fails, trial fails,
    even if subjective LLM judge gave a PASS.
    """
    task = Task(
        id="t2",
        split="dev",
        category="cancellation",
        difficulty="easy",
        user_prompt="test",
        expected=TaskExpected(requires_judge=True),
    )
    graders = [
        GraderResult(grader_name="db_state", status=GraderStatus.FAIL, reason_code="ASSERTION_FAILED", message=""),
        GraderResult(grader_name="policy_critical", status=GraderStatus.PASS, reason_code="OK", message=""),
        GraderResult(grader_name="hallucination", status=GraderStatus.PASS, reason_code="OK", message=""),
        GraderResult(grader_name="llm_judge", status=GraderStatus.PASS, reason_code="GREAT_TONE", message=""),
    ]
    # DB state failed, so overall trial MUST FAIL
    assert compute_trial_outcome(task, graders) == TrialOutcome.FAIL


def test_aggregation_eval_error_priority():
    """Verify any grader ERROR marks trial as EVAL_ERROR rather than blaming agent."""
    task = Task(id="t3", split="dev", category="cancellation", difficulty="easy", user_prompt="test")
    graders = [
        GraderResult(grader_name="db_state", status=GraderStatus.ERROR, reason_code="SQL_ERROR", message=""),
        GraderResult(grader_name="policy_critical", status=GraderStatus.PASS, reason_code="OK", message=""),
    ]
    assert compute_trial_outcome(task, graders) == TrialOutcome.EVAL_ERROR


def test_evaluate_trial_end_to_end():
    """Verify end-to-end multi-grader execution over a trial trajectory."""
    conn = SandboxDB.create_connection()
    task = Task(
        id="task_e2e",
        split="dev",
        category="inquiry",
        difficulty="easy",
        user_prompt="Status of order ORD-101",
        expected=TaskExpected(
            required_tools=["lookup_order"],
            requires_judge=False,
        ),
    )

    trajectory = Trajectory(task_id=task.id, trial_id="tr_e2e")
    trajectory.add_event(
        event_type="MODEL_RESPONSE",
        tool_calls=[{"function": {"name": "lookup_order", "arguments": '{"order_id": "ORD-101"}'}}],
    )
    trajectory.add_event(
        event_type="TOOL_RESULT",
        tool_result={"success": True, "data": {"order_id": "ORD-101", "status": "pending"}},
    )
    trajectory.final_response = "Order ORD-101 is currently pending."

    outcome, results = evaluate_trial(trajectory, task, conn=conn)

    assert outcome == TrialOutcome.PASS
    assert len(results) == 5  # db_state, safety_invariants, policy_critical, hallucination, llm_judge
    assert all(r.status in (GraderStatus.PASS, GraderStatus.NOT_APPLICABLE) for r in results)
