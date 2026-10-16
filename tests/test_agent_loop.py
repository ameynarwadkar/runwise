"""
Tests for AgentLoop: verifies conversation history ordering, multi-step tool
calling, and step-limit bounding using deterministic mock responses.
"""

from types import SimpleNamespace
from runwise.agent.loop import AgentLoop
from runwise.agent.trajectory import ExitReason
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext


def create_mock_message(content: str | None = None, tool_calls: list | None = None):
    """Helper creating an object mirroring LiteLLM/OpenAI completion responses."""
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(prompt_tokens=50, completion_tokens=20)
    return SimpleNamespace(choices=[choice], usage=usage)


def create_mock_tool_call(call_id: str, name: str, arguments: dict):
    """Helper creating a mocked tool call object."""
    func = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, function=func)


def test_agent_single_turn_completion():
    """Verify that an agent returning a text answer without tool calls terminates normally."""
    conn = SandboxDB.create_connection()
    session = SessionContext(conn=conn, trial_id="trial_single", current_time_iso="2026-10-15T12:00:00Z")

    mock_resp = create_mock_message(content="Hello! How can I assist you with your order today?")
    agent = AgentLoop()
    trajectory = agent.run(
        user_prompt="Hi",
        session=session,
        mock_completions=[mock_resp],
    )

    assert trajectory.exit_reason == ExitReason.NORMAL_COMPLETION
    assert trajectory.final_response == "Hello! How can I assist you with your order today?"
    assert len(trajectory.events) == 2  # USER_INPUT + MODEL_RESPONSE
    assert trajectory.events[0].seq == 1
    assert trajectory.events[1].seq == 2


def test_agent_multi_step_tool_calling():
    """
    Verify multi-step tool execution:
    Turn 1: Model calls lookup_order('ORD-101')
    Turn 2: Model receives tool result and provides final text response.
    """
    conn = SandboxDB.create_connection()
    session = SessionContext(conn=conn, trial_id="trial_multi", current_time_iso="2026-10-15T12:00:00Z")

    # Turn 1: request lookup_order
    tc = create_mock_tool_call("tc_001", "lookup_order", {"order_id": "ORD-101"})
    turn1 = create_mock_message(content=None, tool_calls=[tc])

    # Turn 2: answer customer
    turn2 = create_mock_message(content="Order ORD-101 is currently pending with total $100.00.")

    agent = AgentLoop()
    trajectory = agent.run(
        user_prompt="What is the status of my order ORD-101?",
        session=session,
        mock_completions=[turn1, turn2],
    )

    assert trajectory.exit_reason == ExitReason.NORMAL_COMPLETION
    assert "ORD-101 is currently pending" in trajectory.final_response

    # Verify event sequence: USER_INPUT (1), MODEL_RESPONSE (2), TOOL_RESULT (3), MODEL_RESPONSE (4)
    assert len(trajectory.events) == 4
    assert trajectory.events[0].event_type == "USER_INPUT"
    assert trajectory.events[1].event_type == "MODEL_RESPONSE"
    assert trajectory.events[2].event_type == "TOOL_RESULT"
    assert trajectory.events[2].tool_result["success"] is True
    assert trajectory.events[3].event_type == "MODEL_RESPONSE"


def test_agent_max_steps_exceeded():
    """Verify that an agent stuck in a tool loop terminates cleanly with MAX_STEPS_EXCEEDED."""
    conn = SandboxDB.create_connection()
    session = SessionContext(conn=conn, trial_id="trial_loop", current_time_iso="2026-10-15T12:00:00Z")

    # Generate repeated tool calls that exceed max_steps = 3
    tc = create_mock_tool_call("tc_repeat", "lookup_order", {"order_id": "ORD-101"})
    repeating_turn = create_mock_message(content=None, tool_calls=[tc])

    agent = AgentLoop(max_steps=3)
    trajectory = agent.run(
        user_prompt="Check order status",
        session=session,
        mock_completions=[repeating_turn, repeating_turn, repeating_turn, repeating_turn],
    )

    assert trajectory.exit_reason == ExitReason.MAX_STEPS_EXCEEDED
    assert "maximum allowed steps" in trajectory.final_response
