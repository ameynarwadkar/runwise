"""
Core bounded execution loop for the Customer Support Agent.

Uses LiteLLM to interact with Google Gemini or any OpenAI-compatible provider.
Executes function calls against the trial's active SessionContext and records
every step into an immutable Trajectory.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import litellm
import yaml

from runwise.agent.dispatcher import TOOL_SCHEMAS, dispatch_tool_call
from runwise.agent.trajectory import ExitReason, TokenUsage, Trajectory
from runwise.domain.model import SessionContext

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
        model: str = "gemini/gemini-2.5-flash",
        temperature: float = 0.0,
        max_steps: int = 8,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_steps = max_steps
        self.api_key = api_key
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

        # 1. Initialize conversation history
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        trajectory.add_event(event_type="USER_INPUT", content=user_prompt)

        step_count = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        mock_idx = 0

        # 2. Main reasoning loop
        while step_count < self.max_steps:
            step_count += 1

            # Fetch completion: either from mock list or from LiteLLM
            try:
                if mock_completions is not None:
                    if mock_idx >= len(mock_completions):
                        break
                    response = mock_completions[mock_idx]
                    mock_idx += 1
                else:
                    response = litellm.completion(
                        model=self.model,
                        messages=messages,
                        tools=TOOL_SCHEMAS,
                        temperature=self.temperature,
                        api_key=self.api_key,
                    )
            except Exception as e:
                trajectory.exit_reason = ExitReason.PROVIDER_ERROR
                trajectory.final_response = f"Provider error: {e}"
                break

            choice = response.choices[0]
            message = choice.message
            content = message.content or ""

            # Accumulate token metrics if available
            if hasattr(response, "usage") and response.usage:
                total_prompt_tokens += getattr(response.usage, "prompt_tokens", 0)
                total_completion_tokens += getattr(response.usage, "completion_tokens", 0)

            # Check if model invoked tool calls
            tool_calls = getattr(message, "tool_calls", None)

            if not tool_calls:
                # Normal completion: model provided its final user response
                trajectory.final_response = content
                trajectory.exit_reason = ExitReason.NORMAL_COMPLETION
                trajectory.add_event(event_type="MODEL_RESPONSE", content=content)
                break

            # Model requested one or more tool calls
            serialized_tool_calls = [_serialize_tool_call(tc) for tc in tool_calls]
            trajectory.add_event(
                event_type="MODEL_RESPONSE",
                content=content,
                tool_calls=serialized_tool_calls,
            )

            # Append the assistant message with its tool_calls to conversation history
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": serialized_tool_calls,
                }
            )

            # Execute each requested tool call
            for tc in tool_calls:
                tool_id = getattr(tc, "id", "tool_call_unknown")
                func = getattr(tc, "function")
                tool_name = getattr(func, "name")
                tool_args = getattr(func, "arguments")

                # Dispatch tool call against active session context
                result = dispatch_tool_call(session, tool_name, tool_args)

                # Record event in trajectory
                trajectory.add_event(
                    event_type="TOOL_RESULT",
                    content=f"Tool {tool_name} returned status={result.success}",
                    tool_result=result.model_dump(),
                )

                # Append tool result to conversation history matching tool_call_id
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "name": tool_name,
                        "content": json.dumps(result.model_dump()),
                    }
                )

        else:
            # Exited while loop because step_count reached max_steps
            trajectory.exit_reason = ExitReason.MAX_STEPS_EXCEEDED
            trajectory.final_response = "I was unable to complete your request within the maximum allowed steps."

        # 3. Finalize latency and usage metrics
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        trajectory.usage = TokenUsage(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            latency_ms=elapsed_ms,
        )

        return trajectory
