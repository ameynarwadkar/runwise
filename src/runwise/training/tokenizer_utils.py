"""
Tokenizer utilities, prompt serialization, and assistant-only loss masking for Qwen3 SFT.

Implements:
1. Canonical ChatML formatting with Qwen XML tool tags (<tools>, <tool_call>, <tool_response>, <think>).
2. Character offset-aware assistant-only token loss masking:
   - System prompt, user queries, and tool execution returns receive labels = -100.
   - Assistant turns (content, tool_call JSON) and terminal <|im_end|> tokens receive active loss.
3. Configurable thinking-mode output masking (<think>...</think> can be masked to -100 or kept).
4. Strict sequence length truncation and active loss ratio metrics.
"""

from __future__ import annotations

import json
import re
from typing import Any

from runwise.training.schemas import SFTExample

IM_START = "<|im_start|>"
IM_END = "<|im_end|>"
IGNORE_INDEX = -100


def compute_assistant_spans(text: str) -> list[tuple[int, int]]:
    """
    Computes (start_char, end_char) spans for assistant responses,
    starting immediately after `<|im_start|>assistant\n` and extending through `<|im_end|>`.
    """
    spans: list[tuple[int, int]] = []
    pattern = re.compile(r"<\|im_start\|>assistant\n(.*?)<\|im_end\|>", re.DOTALL)
    for m in pattern.finditer(text):
        spans.append((m.start(1), m.end()))
    return spans


def compute_think_spans(text: str) -> list[tuple[int, int]]:
    """
    Computes (start_char, end_char) spans for `<think>...</think>` reasoning blocks.
    Includes any immediate trailing newline.
    """
    spans: list[tuple[int, int]] = []
    pattern = re.compile(r"<think>(.*?)</think>\s*", re.DOTALL)
    for m in pattern.finditer(text):
        spans.append((m.start(), m.end()))
    return spans


class QwenLossMasker:
    """
    Computes assistant-only loss masking for Qwen ChatML sequences.
    """

    @classmethod
    def format_example_to_text(cls, example: SFTExample) -> str:
        """
        Converts an SFTExample into the exact Qwen ChatML text sequence.
        """
        parts: list[str] = []

        # 1. System Prompt + Tools Declaration
        system_content = example.messages[0].content or "You are a helpful customer support assistant."
        tools_decl = (
            f"\n\n# Tools\n\n"
            f"You may call one or more functions to assist with the user query.\n"
            f"You are provided with function signatures within <tools></tools> XML tags:\n"
            f"<tools>\n"
            f"{json.dumps(example.tools, indent=2)}\n"
            f"</tools>\n\n"
            f"For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n"
            f"<tool_call>\n"
            f'{{"name": <function-name>, "arguments": <args-json-object>}}\n'
            f"</tool_call>"
        )
        parts.append(f"{IM_START}system\n{system_content.strip()}{tools_decl}{IM_END}")

        # 2. Conversation turns
        for msg in example.messages[1:]:
            role = msg.role
            content = msg.content or ""

            if role == "user":
                parts.append(f"{IM_START}user\n{content}{IM_END}")

            elif role == "assistant":
                if msg.tool_calls:
                    call_strs = []
                    for tc in msg.tool_calls:
                        args = tc.function.arguments
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                pass
                        call_dict = {"name": tc.function.name, "arguments": args}
                        call_strs.append(f"<tool_call>\n{json.dumps(call_dict)}\n</tool_call>")
                    calls_text = "\n".join(call_strs)
                    if content:
                        parts.append(f"{IM_START}assistant\n{content}\n{calls_text}{IM_END}")
                    else:
                        parts.append(f"{IM_START}assistant\n{calls_text}{IM_END}")
                else:
                    parts.append(f"{IM_START}assistant\n{content}{IM_END}")

            elif role == "tool":
                tool_resp = f"<tool_response>\n{content}\n</tool_response>"
                parts.append(f"{IM_START}user\n{tool_resp}{IM_END}")

        return "\n".join(parts)

    @classmethod
    def create_masked_labels(
        cls,
        token_ids: list[int],
        tokens: list[str],
        mask_think_tokens: bool = False,
    ) -> list[int]:
        """
        Creates label tensor where only assistant tokens are unmasked (tokenizer-free fallback).
        """
        labels = [IGNORE_INDEX] * len(token_ids)
        in_assistant = False
        in_think = False

        i = 0
        while i < len(tokens):
            tok = tokens[i]

            if "<|im_start|>" in tok:
                if "assistant" in tok:
                    in_assistant = True
                    i += 1
                    continue
                elif i + 1 < len(tokens) and "assistant" in tokens[i + 1]:
                    in_assistant = True
                    i += 2
                    continue
                else:
                    in_assistant = False

            if tok == IM_END or "<|im_end|>" in tok:
                if in_assistant:
                    labels[i] = token_ids[i]
                in_assistant = False
                in_think = False
                i += 1
                continue

            if "<think>" in tok or "<th" in tok:
                in_think = True
            if "</think>" in tok:
                in_think = False

            if in_assistant:
                if mask_think_tokens and in_think:
                    labels[i] = IGNORE_INDEX
                else:
                    labels[i] = token_ids[i]

            i += 1

        return labels

    @classmethod
    def mask_with_offsets(
        cls,
        text: str,
        input_ids: list[int],
        offset_mapping: list[tuple[int, int]],
        mask_think_tokens: bool = False,
    ) -> list[int]:
        """
        Computes exact assistant-only labels using tokenizer character offset mapping.
        Immune to arbitrary BPE subword splitting.
        """
        labels = [IGNORE_INDEX] * len(input_ids)
        asst_spans = compute_assistant_spans(text)
        think_spans = compute_think_spans(text)

        for i, ((c_start, c_end), tid) in enumerate(zip(offset_mapping, input_ids)):
            if c_start == c_end:
                continue

            in_asst = any(s <= c_start and c_end <= e for s, e in asst_spans)
            if in_asst:
                in_thk = any(s <= c_start and c_end <= e for s, e in think_spans)
                if mask_think_tokens and in_thk:
                    labels[i] = IGNORE_INDEX
                else:
                    labels[i] = tid
            else:
                labels[i] = IGNORE_INDEX

        return labels

    @classmethod
    def process_example(
        cls,
        example: SFTExample,
        tokenizer: Any | None = None,
        max_seq_length: int = 2048,
        mask_think_tokens: bool = False,
    ) -> dict[str, Any]:
        """
        Formats and tokenizes an SFT example with assistant-only loss masking.
        """
        full_text = cls.format_example_to_text(example)

        if tokenizer is not None:
            encoded = tokenizer(
                full_text,
                add_special_tokens=False,
                return_offsets_mapping=True,
            )
            input_ids = encoded["input_ids"]
            offset_mapping = encoded.get("offset_mapping")
            if offset_mapping:
                labels = cls.mask_with_offsets(
                    text=full_text,
                    input_ids=input_ids,
                    offset_mapping=offset_mapping,
                    mask_think_tokens=mask_think_tokens,
                )
            else:
                tokens = [tokenizer.decode([tid]) for tid in input_ids]
                labels = cls.create_masked_labels(
                    token_ids=input_ids,
                    tokens=tokens,
                    mask_think_tokens=mask_think_tokens,
                )
        else:
            raw_tokens = []
            for part in full_text.split("\n"):
                for sub in part.split(" "):
                    if sub:
                        raw_tokens.append(sub)
            input_ids = list(range(len(raw_tokens)))
            tokens = raw_tokens
            labels = cls.create_masked_labels(
                token_ids=input_ids,
                tokens=tokens,
                mask_think_tokens=mask_think_tokens,
            )

        truncated = len(input_ids) > max_seq_length
        if truncated:
            input_ids = input_ids[:max_seq_length]
            labels = labels[:max_seq_length]

        active_loss_tokens = sum(1 for lab in labels if lab != IGNORE_INDEX)
        total_tokens = len(input_ids)
        active_ratio = round(active_loss_tokens / total_tokens, 4) if total_tokens else 0.0

        return {
            "example_id": example.example_id,
            "full_text": full_text,
            "input_ids": input_ids,
            "labels": labels,
            "attention_mask": [1] * len(input_ids),
            "total_tokens": total_tokens,
            "active_loss_tokens": active_loss_tokens,
            "active_loss_ratio": active_ratio,
            "truncated": truncated,
        }
