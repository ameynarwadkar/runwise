"""
Qwen3-1.7B model adapter, prompt formatter, and tool-call parser.

Translates between Runwise OpenAI-style message dictionaries and
the official Qwen XML tool-calling chat template (<tools>, <tool_call>, <tool_response>, <think>).
"""

from __future__ import annotations

import json
import re
import uuid
from types import SimpleNamespace
from typing import Any, Callable


class QwenToolCallParser:
    """
    Parses Qwen3 model outputs containing XML-wrapped function calls and thinking blocks.
    Cleanly strips thinking tags, tool_call XML envelopes, and residual ChatML special tokens (<|im_end|>, <|im_start|>, etc.).
    """

    THINK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL)
    TOOL_CALL_REGEX = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
    HEADER_REGEX = re.compile(r"<\|im_start\|>\s*(assistant|user|system)?\s*", re.IGNORECASE)
    SPECIAL_TOKENS_REGEX = re.compile(r"<\|[a-zA-Z0-9_\-]+\|>", re.DOTALL)

    @classmethod
    def parse(cls, raw_output: str) -> tuple[str, list[dict[str, Any]], str | None]:
        """
        Parses raw model output.

        Returns:
        --------
        tuple of:
        - cleaned_content: Text outside <think>, <tool_call>, and special tokens.
        - tool_calls: List of standardized OpenAI-compatible tool call dicts.
        - think_content: Text inside <think> tags, or None if absent.
        """
        think_match = cls.THINK_REGEX.search(raw_output)
        think_content = think_match.group(1).strip() if think_match else None

        # Remove think blocks for clean text processing
        text_without_think = cls.THINK_REGEX.sub("", raw_output)

        tool_calls: list[dict[str, Any]] = []
        for match in cls.TOOL_CALL_REGEX.finditer(text_without_think):
            payload_str = match.group(1).strip()
            try:
                payload = json.loads(payload_str)
                name = payload.get("name")
                raw_args = payload.get("arguments", {})
                if not name:
                    continue

                args_str = json.dumps(raw_args) if isinstance(raw_args, dict) else str(raw_args)
                tool_calls.append({
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": args_str,
                    },
                })
            except Exception:
                # Malformed JSON payload inside tool call
                continue

        # Clean remaining text of tool_call blocks, role headers, and residual special tokens (<|im_end|>, <|im_start|>, etc.)
        cleaned_content = cls.TOOL_CALL_REGEX.sub("", text_without_think)
        cleaned_content = cls.HEADER_REGEX.sub("", cleaned_content)
        cleaned_content = cls.SPECIAL_TOKENS_REGEX.sub("", cleaned_content).strip()

        return cleaned_content, tool_calls, think_content


def parse_qwen_tool_calls(raw_output: str) -> tuple[str, list[dict[str, Any]], str | None]:
    """Convenience function for QwenToolCallParser.parse."""
    return QwenToolCallParser.parse(raw_output)


def format_qwen_chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> str:
    """
    Renders messages and tools into the official Qwen ChatML string format.
    
    Structure:
    <|im_start|>system
    {system_content}
    
    # Tools
    You may call one or more functions to assist with the user query...
    <tools>
    {tools_json}
    </tools>
    ...
    <|im_end|>
    """
    formatted_parts: list[str] = []

    # Find or prepare system message
    system_content = ""
    start_idx = 0
    if messages and messages[0].get("role") == "system":
        system_content = messages[0].get("content", "") or ""
        start_idx = 1

    if tools:
        tools_decl = (
            f"\n\n# Tools\n\n"
            f"You may call one or more functions to assist with the user query.\n"
            f"You are provided with function signatures within <tools></tools> XML tags:\n"
            f"<tools>\n"
            f"{json.dumps(tools, indent=2)}\n"
            f"</tools>\n\n"
            f"For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n"
            f"<tool_call>\n"
            f'{{"name": <function-name>, "arguments": <args-json-object>}}\n'
            f"</tool_call>"
        )
        full_system = f"{system_content}{tools_decl}".strip()
    else:
        full_system = system_content.strip()

    if full_system:
        formatted_parts.append(f"<|im_start|>system\n{full_system}<|im_end|>")

    for msg in messages[start_idx:]:
        role = msg.get("role")
        content = msg.get("content") or ""

        if role == "user":
            formatted_parts.append(f"<|im_start|>user\n{content}<|im_end|>")

        elif role == "assistant":
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                call_blocks = []
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    fn_args = fn.get("arguments", "{}")
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            pass
                    call_dict = {"name": fn_name, "arguments": fn_args}
                    call_blocks.append(f"<tool_call>\n{json.dumps(call_dict)}\n</tool_call>")
                joined_calls = "\n".join(call_blocks)
                if content:
                    formatted_parts.append(f"<|im_start|>assistant\n{content}\n{joined_calls}<|im_end|>")
                else:
                    formatted_parts.append(f"<|im_start|>assistant\n{joined_calls}<|im_end|>")
            else:
                formatted_parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")

        elif role == "tool":
            # In Qwen template, tool responses are wrapped in <tool_response> under user role
            tool_resp = f"<tool_response>\n{content}\n</tool_response>"
            formatted_parts.append(f"<|im_start|>user\n{tool_resp}<|im_end|>")

    return "\n".join(formatted_parts)


class QwenAdapter:
    """
    Adapter that integrates Qwen3-1.7B with Runwise's AgentLoop.
    Implements a .complete(...) method compatible with LiteLLM / ModelGateway.
    """

    def __init__(
        self,
        generate_fn: Callable[[str], str] | None = None,
        model_name: str = "Qwen/Qwen3-1.7B",
    ):
        self.generate_fn = generate_fn
        self.model_name = model_name

    def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        api_key: str | None = None,
    ) -> SimpleNamespace:
        """
        Executes completion by formatting messages into Qwen format,
        invoking the generation function, and parsing output into standard OpenAI choice/message.
        """
        prompt_text = format_qwen_chat(messages, tools=tools)

        if self.generate_fn is not None:
            raw_output = self.generate_fn(prompt_text)
        else:
            raw_output = "No generation function provided to QwenAdapter."

        cleaned_content, tool_calls, think_content = QwenToolCallParser.parse(raw_output)

        message_obj = SimpleNamespace(
            role="assistant",
            content=cleaned_content if cleaned_content else None,
            tool_calls=tool_calls if tool_calls else None,
            thought=think_content,
        )

        choice_obj = SimpleNamespace(message=message_obj, finish_reason="stop" if not tool_calls else "tool_calls")
        return SimpleNamespace(
            choices=[choice_obj],
            usage=SimpleNamespace(prompt_tokens=len(prompt_text.split()), completion_tokens=len(raw_output.split())),
        )
