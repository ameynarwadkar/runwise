"""
Validates OpenAI tool schema structure and tool call dispatching.
"""

from runwise.agent.dispatcher import TOOL_SCHEMAS, dispatch_tool_call
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext


def create_test_session() -> SessionContext:
    """Helper to spin up an ephemeral sandbox connection."""
    conn = SandboxDB.create_connection()
    return SessionContext(
        conn=conn,
        trial_id="trial_dispatcher_test",
        current_time_iso="2026-10-15T12:00:00Z",
    )


def test_tool_schemas_structure():
    """Verify all 8 tool schemas conform to OpenAI function specification."""
    assert len(TOOL_SCHEMAS) == 8
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        fn = schema["function"]
        assert "name" in fn and len(fn["name"]) > 0
        assert "description" in fn and len(fn["description"]) > 0
        assert "parameters" in fn
        assert schema["function"]["parameters"]["type"] == "object"


def test_dispatch_valid_read_tool():
    """Verify dispatcher executes lookup_order with dictionary arguments."""
    session = create_test_session()
    result = dispatch_tool_call(session, "lookup_order", {"order_id": "ORD-101"})

    assert result.success is True
    assert result.data["order"]["order_id"] == "ORD-101"
    assert result.data["order"]["status"] == "pending"


def test_dispatch_with_json_string_arguments():
    """Verify dispatcher safely parses raw JSON string arguments from an LLM."""
    session = create_test_session()
    raw_json = '{"order_id": "ORD-101"}'
    result = dispatch_tool_call(session, "lookup_order", raw_json)

    assert result.success is True
    assert result.data["order"]["order_id"] == "ORD-101"


def test_dispatch_unknown_tool():
    """Verify dispatcher safely handles hallucinated tool names."""
    session = create_test_session()
    result = dispatch_tool_call(session, "hack_the_system", {"target": "all"})

    assert result.success is False
    assert result.error_code == "UNKNOWN_TOOL"


def test_dispatch_malformed_json_arguments():
    """Verify dispatcher catches malformed JSON without raising unhandled exceptions."""
    session = create_test_session()
    result = dispatch_tool_call(session, "lookup_order", "{not_valid_json: 123")

    assert result.success is False
    assert result.error_code == "INVALID_JSON_ARGUMENTS"
