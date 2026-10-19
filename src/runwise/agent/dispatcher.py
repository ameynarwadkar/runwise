"""
OpenAI-compatible tool schemas and dispatcher for model function calls.

Translates incoming tool calls from LiteLLM into domain tool invocations against
the trial's active SessionContext.
"""

from __future__ import annotations

import json
from typing import Any

from runwise.domain import tools
from runwise.domain.model import SessionContext, ToolResult

# ============================================================================
# OPENAI-COMPATIBLE TOOL SCHEMAS FOR LITELLM
# ============================================================================

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_user",
            "description": "Look up public customer profile by user_id or email. Does not authenticate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Customer ID (e.g. 'CUST-001')"},
                    "email": {"type": "string", "description": "Customer email address"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_customer",
            "description": "Verify customer identity with 4-digit code. Authorizes session for mutations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Customer ID (e.g. 'CUST-001')"},
                    "verification_code": {"type": "string", "description": "4-digit verification code"},
                },
                "required": ["user_id", "verification_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Fetch order details, status, line items, and existing refund history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID (e.g. 'ORD-101')"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_shipping_address",
            "description": "Update delivery address for a pending order. Requires customer authentication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to update"},
                    "new_address": {"type": "string", "description": "New delivery address"},
                    "idempotency_key": {"type": "string", "description": "Unique key to prevent duplicate updates"},
                },
                "required": ["order_id", "new_address", "idempotency_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_order",
            "description": "Cancel an order in pending status. Requires customer authentication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to cancel"},
                    "reason": {"type": "string", "description": "Reason for cancellation"},
                    "idempotency_key": {"type": "string", "description": "Unique key to prevent duplicate cancellation"},
                },
                "required": ["order_id", "reason", "idempotency_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Issue refund for delivered order within 30 days. Requires customer authentication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to refund"},
                    "amount_cents": {"type": "integer", "description": "Refund amount in integer cents (e.g. 2500 for $25.00)"},
                    "reason": {"type": "string", "description": "Reason for refund"},
                    "idempotency_key": {"type": "string", "description": "Unique key to prevent duplicate refunds"},
                },
                "required": ["order_id", "amount_cents", "reason", "idempotency_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_policy",
            "description": "Retrieve official customer support policy rules and excerpts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Policy topic (e.g. 'refunds', 'cancellations')"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_orders",
            "description": "List all order summaries for the authenticated customer. Requires customer authentication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Optional customer ID. Must match the authenticated customer ID."},
                },
            },
        },
    },
]


# ============================================================================
# TOOL CALL DISPATCHER
# ============================================================================

_DISPATCH_TABLE = {
    "lookup_user": tools.lookup_user,
    "verify_customer": tools.verify_customer,
    "lookup_order": tools.lookup_order,
    "list_orders": tools.list_orders,
    "update_shipping_address": tools.update_shipping_address,
    "cancel_order": tools.cancel_order,
    "issue_refund": tools.issue_refund,
    "lookup_policy": tools.lookup_policy,
}


def dispatch_tool_call(
    session: SessionContext,
    tool_name: str | None = None,
    arguments: dict[str, Any] | str | None = None,
    *,
    fn_name: str | None = None,
    fn_args: dict[str, Any] | str | None = None,
) -> ToolResult:
    """
    Safely executes a model tool call against the active session.
    
    1. Resolves tool name and arguments (supporting both tool_name/arguments and fn_name/fn_args).
    2. Deserializes arguments if provided as a raw JSON string.
    3. Verifies the tool name exists in the dispatch table.
    4. Passes `session` and parsed kwargs to the corresponding domain function.
    5. Catches argument mismatches and unexpected errors without crashing.
    """
    target_tool_name = tool_name or fn_name or ""
    raw_arguments = arguments if arguments is not None else (fn_args if fn_args is not None else {})

    # 1. Parse JSON string arguments from model if necessary
    if isinstance(raw_arguments, str):
        try:
            parsed_args = json.loads(raw_arguments) if raw_arguments.strip() else {}
        except Exception as e:
            return ToolResult(
                success=False,
                error_code="INVALID_JSON_ARGUMENTS",
                error_message=f"Failed to parse tool arguments: {e}",
            )
    else:
        parsed_args = raw_arguments or {}

    # 2. Verify tool exists
    func = _DISPATCH_TABLE.get(target_tool_name)
    if not func:
        return ToolResult(
            success=False,
            error_code="UNKNOWN_TOOL",
            error_message=f"Tool '{target_tool_name}' is not recognized by the system.",
        )

    # 3. Execute domain tool with session context
    try:
        return func(session, **parsed_args)
    except TypeError as e:
        return ToolResult(
            success=False,
            error_code="ARGUMENT_MISMATCH",
            error_message=f"Invalid arguments for tool '{tool_name}': {e}",
        )
    except Exception as e:
        return ToolResult(
            success=False,
            error_code="DISPATCH_ERROR",
            error_message=f"Unexpected error executing '{tool_name}': {e}",
        )
