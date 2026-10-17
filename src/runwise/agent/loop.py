"""
Core bounded execution loop for the Customer Support Agent.

Uses LiteLLM to interact with Google Gemini or any OpenAI-compatible provider.
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
from runwise.observability.tracer import trace_span

# Path to the versioned system prompt template
PROMPT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "agent" / "v1.0.yaml"


def _load_system_prompt() -> str:
    """Loads the system prompt from the versioned YAML configuration."""
    if not PROMPT_PATH.exists():
        return "You are a customer support agent. Help customers accurately."
    config = yaml.safe_load(PROMPT_PATH.read_text(encoding="utf-8"))
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
        func.model_dump() if hasattr(func, "model_dump")
        else vars(func) if hasattr(func, "__dict__")
        else func if isinstance(func, dict)
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
        max_steps: int = 8,
        api_key: str | None = None,
    ) -> None:
        cfg = get_provider_config(override_model=model)
        self.model = cfg.model_identifier
        self.temperature = temperature
        self.max_steps = max_steps
        self.api_key = cfg.api_key or api_key
        self.system_prompt = _load_system_prompt()

    def run(
        self,
        user_prompt: str,
        session: SessionContext,
        task_id: str = "task_adhoc",
        mock_completions: list[Any] | None = None,
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
        """
        start_time = time.perf_counter()
        trajectory = Trajectory(
            task_id=task_id,
            trial_id=session.trial_id,
            metadata={
                "model": self.model,
                "temperature": self.temperature,
                "max_steps": self.max_steps,
            },
        )
        
        with trace_span(
            name=f"agent_run:{task_id}",
            span_kind="AGENT",
            input_value=user_prompt,
            attributes={
                "task.id": task_id,
                "trial.id": session.trial_id,
                "model": self.model,
            },
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
            start_time = time.perf_counter()
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
                        last_msg = messages[-1]["content"] if messages else ""
                        with trace_span(
                            name=f"llm_completion:step_{step_count}",
                            span_kind="LLM",
                            input_value=last_msg,
                            attributes={"step": step_count, "model": self.model},
                        ) as llm_span:
                            response = litellm.completion(
                                model=self.model,
                                messages=messages,
                                tools=TOOL_SCHEMAS,
                                temperature=self.temperature,
                                api_key=self.api_key,
                            )
                            c_msg = response.choices[0].message
                            llm_span.set_output(
                                c_msg.content or [getattr(tc.function, "name", "") for tc in getattr(c_msg, "tool_calls", None) or []]
                            )
                except Exception as e:
                    trajectory.exit_reason = ExitReason.PROVIDER_ERROR
                    trajectory.final_response = f"Provider error: {e}"
                    break
                choice = response.choices[0]
                message = choice.message
                content = message.content or ""
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
                        "tool_calls": serialized_calls,
                    })
                    for tc in tool_calls:
                        func_name = getattr(tc.function, "name", "")
                        func_args_str = getattr(tc.function, "arguments", "{}")
                        tc_id = getattr(tc, "id", None) or f"call_{uuid.uuid4().hex[:8]}"
                        with trace_span(
                            name=f"tool_dispatch:{func_name}",
                            span_kind="TOOL",
                            input_value=func_args_str,
                            attributes={"tool.name": func_name, "tool_call_id": tc_id},
                        ) as tool_span:
                            tool_result = dispatch_tool_call(
                                session=session,
                                tool_name=func_name,
                                arguments=func_args_str,
                            )
                            tool_span.set_output(tool_result.model_dump())
                        trajectory.add_event(
                            event_type="TOOL_RESULT",
                            content=f"Tool {func_name} returned status={tool_result.success}",
                            tool_result=tool_result.model_dump(),
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": json.dumps(tool_result.model_dump()),
                        })
                else:
                    trajectory.add_event(
                        event_type="MODEL_RESPONSE",
                        content=content,
                    )
                    trajectory.final_response = content
                    trajectory.exit_reason = ExitReason.NORMAL_COMPLETION
                    break
            else:
                trajectory.exit_reason = ExitReason.MAX_STEPS_EXCEEDED
                trajectory.final_response = "I was unable to complete your request within the maximum allowed steps."

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            trajectory.usage = TokenUsage(
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                total_tokens=total_prompt_tokens + total_completion_tokens,
                total_cost_usd=0.0,
                latency_ms=latency_ms,
            )
            agent_span.set_output(trajectory.final_response)
            return trajectory