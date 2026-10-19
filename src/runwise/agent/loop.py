"""
Core bounded execution loop for the Customer Support Agent.

Uses LiteLLM (or ModelGateway) to interact with Google Gemini or any OpenAI-compatible provider.
Executes function calls against the trial's active SessionContext and records
every step into an immutable Trajectory.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import litellm
import yaml

from runwise.agent.dispatcher import TOOL_SCHEMAS, dispatch_tool_call
from runwise.agent.trajectory import ExitReason, TokenUsage, Trajectory
from runwise.config import get_provider_config
from runwise.domain.model import SessionContext
from runwise.domain.authorization import ActionScope, ORDER_ID_PATTERN, classify_request_intent
from runwise.observability.tracer import trace_span

# Path to the versioned system prompt template
PROMPT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "agent" / "v1.0.yaml"

# Path to versioned prompts directory
PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "agent"

def _load_system_prompt(version: str = "v1.0") -> str:
    """Loads the system prompt from the versioned YAML configuration."""
    clean_ver = version if version.endswith(".yaml") else f"{version}.yaml"
    target = PROMPTS_DIR / clean_ver
    if not target.exists():
        target = PROMPTS_DIR / "v1.0.yaml"
    if not target.exists():
        return "You are a customer support agent. Help customers accurately."
    config = yaml.safe_load(target.read_text(encoding="utf-8"))
    return config.get("system_prompt", "You are a customer support agent.")


def _serialize_tool_call(tc: Any) -> dict[str, Any]:
    """Converts a LiteLLM tool call or mock object into a standard dictionary."""
    if isinstance(tc, dict):
        return tc
    if hasattr(tc, "model_dump"):
        return tc.model_dump()

    # Handle mock SimpleNamespace objects in tests
    func = getattr(tc, "function", None)
    func_dict = (
        func.model_dump()
        if hasattr(func, "model_dump")
        else vars(func)
        if hasattr(func, "__dict__")
        else func
        if isinstance(func, dict)
        else {}
    )
    return {
        "id": getattr(tc, "id", "tool_call_unknown"),
        "type": "function",
        "function": func_dict,
    }


class AgentLoop:
    """Manages the step-by-step reasoning and tool-calling execution of an agent."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.0,
        max_steps: int = 10,
        system_prompt: str | None = None,
        prompt_version: str = "v1.0",
        gateway: str | None = None,
        api_key: str | None = None,
    ):
        cfg = get_provider_config(override_model=model)
        self.model = cfg.model_identifier
        self.temperature = temperature
        self.max_steps = max_steps
        self.prompt_version = prompt_version
        self.system_prompt = system_prompt or _load_system_prompt(prompt_version)
        self.gateway = gateway
        self.api_key = cfg.api_key or api_key

    def run(
        self,
        user_prompt: str,
        session: SessionContext,
        task_id: str = "task_adhoc",
        mock_completions: list[Any] | None = None,
        request_id: str | None = None,
    ) -> Trajectory:
        """
        Executes the agent loop until the model presents a final response,
        exhausts max_steps, or encounters an unrecoverable error.

        Parameters:
        -----------
        user_prompt: The customer's request.
        session: Active trial SessionContext with in-memory DB and clock.
        task_id: Identifier of the task being evaluated.
        mock_completions: Optional list of mocked responses for deterministic unit tests.
        request_id: Optional HTTP correlation request ID for distributed tracing.
        """
        start_time = time.perf_counter()
        trajectory_metadata = {
            "model": self.model,
            "temperature": self.temperature,
            "max_steps": self.max_steps,
        }
        if request_id:
            trajectory_metadata["request_id"] = request_id

        # Classify user prompt intent and grant explicit transaction authorization if directive
        intent = classify_request_intent(user_prompt)
        session.request_intent = intent.intent_type
        order_matches = set(m.upper() for m in ORDER_ID_PATTERN.findall(user_prompt))

        if intent.is_explicit_transaction and intent.authorized_actions:
            for act_type, oid in intent.authorized_actions:
                session.authorize_action(act_type, oid, scope=intent.action_scope)
        else:
            # Informational inquiry, ambiguous scope, or partial cancellation:
            # Strictly record restricted scope for all referenced orders so whole-order cancellation fails closed
            for oid in order_matches:
                session.set_action_scope("cancel_order", oid, intent.action_scope)

        trajectory = Trajectory(
            task_id=task_id,
            trial_id=session.trial_id,
            metadata=trajectory_metadata,
        )

        span_attributes = {
            "task.id": task_id,
            "trial.id": session.trial_id,
            "model": self.model,
        }
        if request_id:
            span_attributes["http.request_id"] = request_id

        with trace_span(
            name=f"agent_run:{task_id}",
            span_kind="AGENT",
            input_value=user_prompt,
            attributes=span_attributes,
        ) as agent_span:
            # 1. Initialize conversation history with system prompt & simulation clock context
            system_content = (
                f"{self.system_prompt}\n\n"
                f"CURRENT CONTEXT:\n"
                f"- Current Time: {session.current_time_iso}"
            )
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt},
            ]
            trajectory.add_event(
                event_type="USER_INPUT",
                content=user_prompt,
            )
            step_count = 0
            total_prompt_tokens = 0
            total_completion_tokens = 0
            mock_idx = 0

            # 2. Main reasoning loop
            while step_count < self.max_steps:
                step_count += 1
                try:
                    if mock_completions is not None:
                        if mock_idx >= len(mock_completions):
                            break
                        response = mock_completions[mock_idx]
                        mock_idx += 1
                    else:
                        with trace_span(
                            name=f"llm_completion:step_{step_count}",
                            span_kind="LLM",
                            input_value=messages,
                            attributes={"step": step_count, "model": self.model},
                        ) as llm_span:
                            # Route completion through ModelGateway if available, else LiteLLM directly
                            if self.gateway is not None:
                                response = self.gateway.complete(
                                    model=self.model,
                                    messages=messages,
                                    tools=TOOL_SCHEMAS,
                                    temperature=self.temperature,
                                    api_key=self.api_key,
                                )
                            else:
                                response = litellm.completion(
                                    model=self.model,
                                    messages=messages,
                                    tools=TOOL_SCHEMAS,
                                    temperature=self.temperature,
                                    api_key=self.api_key,
                                )
                            raw_msg = response.choices[0].message
                            raw_content = getattr(raw_msg, "content", None) or ""
                            raw_tcs = getattr(raw_msg, "tool_calls", None) or []
                            tc_names = [_serialize_tool_call(tc)["function"]["name"] for tc in raw_tcs]
                            llm_span.set_output(raw_content or tc_names)
                except Exception as exc:
                    trajectory.exit_reason = ExitReason.PROVIDER_ERROR
                    trajectory.final_response = f"I encountered an error communicating with the provider: {exc}"
                    break

                choice = response.choices[0]
                message = choice.message
                content = getattr(message, "content", None) or ""

                if hasattr(response, "usage") and response.usage:
                    total_prompt_tokens += getattr(response.usage, "prompt_tokens", 0)
                    total_completion_tokens += getattr(response.usage, "completion_tokens", 0)

                tool_calls = getattr(message, "tool_calls", None)
                if tool_calls and len(tool_calls) > 0:
                    serialized_calls = [_serialize_tool_call(tc) for tc in tool_calls]
                    trajectory.add_event(
                        event_type="MODEL_RESPONSE",
                        content=content,
                        tool_calls=serialized_calls,
                    )
                    messages.append({
                        "role": "assistant",
                        "content": content,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["function"]["name"],
                                    "arguments": json.dumps(tc["function"]["arguments"])
                                    if isinstance(tc["function"]["arguments"], dict)
                                    else str(tc["function"]["arguments"]),
                                },
                            }
                            for tc in serialized_calls
                        ],
                    })

                    # Dispatch each requested tool call
                    for tc in serialized_calls:
                        call_id = tc["id"]
                        fn_name = tc["function"]["name"]
                        fn_args = tc["function"]["arguments"]

                        with trace_span(
                            name=f"tool_dispatch:{fn_name}",
                            span_kind="TOOL",
                            input_value=fn_args,
                            attributes={"tool.name": fn_name, "tool_call_id": call_id},
                        ) as tool_span:
                            result = dispatch_tool_call(
                                session=session,
                                tool_name=fn_name,
                                arguments=fn_args,
                            )
                            tool_span.set_output(result.model_dump())

                        trajectory.add_event(
                            event_type="TOOL_RESULT",
                            content=f"Tool {fn_name} returned status={result.success}",
                            tool_result=result.model_dump(),
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": fn_name,
                            "content": json.dumps(result.model_dump()),
                        })
                else:
                    # Final assistant answer
                    trajectory.add_event(
                        event_type="MODEL_RESPONSE",
                        content=content,
                    )
                    trajectory.exit_reason = ExitReason.NORMAL_COMPLETION
                    trajectory.final_response = content
                    break
            else:
                trajectory.exit_reason = ExitReason.MAX_STEPS_EXCEEDED
                trajectory.final_response = "I was unable to complete your request within the maximum allowed steps."

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            trajectory.usage = TokenUsage(
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                total_tokens=total_prompt_tokens + total_completion_tokens,
                total_cost_usd=0.0,
                latency_ms=elapsed_ms,
            )
            agent_span.set_output(trajectory.final_response)
            return trajectory
