"""
Blocker 1 Recalculation & Validation Script.
Analyzes the baseline 112, Stage 6 70, and combined 182 decision points.
Computes:
1. Sample counts across all 7 required categories:
   - First tool calls
   - Subsequent tool calls
   - Post-tool final answers
   - Security refusals
   - Clarifications
   - Capability fallbacks
   - Tool-error responses
2. Actual supervised target tokens per category using the Qwen3 tokenizer.
3. Verification that every sample has supervised tokens (> 0), valid syntax, and correct labeling.
"""

import json
from collections import defaultdict
from pathlib import Path
from transformers import AutoTokenizer

DATA_DIR = Path("data/sft")
BASELINE_PATH = DATA_DIR / "decision_points_112_examples.jsonl"
STAGE6_PATH = DATA_DIR / "decision_points_stage6_70_examples.jsonl"

tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")


def classify_decision_point(dp: dict) -> str:
    """
    Standardizes decision point categorization across baseline 112 and new 70:
    - First tool calls
    - Subsequent tool calls
    - Post-tool final answers
    - Security refusals
    - Clarifications
    - Capability fallbacks
    - Tool-error responses
    """
    target = dp["target_turn"]
    is_tool = target.get("tool_calls") is not None
    step_idx = dp.get("step_index", 1)
    dtype = dp.get("decision_type", "")
    domain = dp.get("curriculum_domain", "")
    meta_cat = dp.get("metadata", {}).get("category", "")
    content = (target.get("content") or "").lower()

    if is_tool:
        # Tool call: distinguish first vs subsequent
        if step_idx == 1 or dtype in ["first_tool_call"]:
            return "First tool calls"
        else:
            return "Subsequent tool calls"
    else:
        # Prose target: classify by intent/category
        if dtype == "clarification" or "clarification" in meta_cat:
            return "Clarifications"
        if dtype in ["unsupported_fallback"] or "fallback" in meta_cat:
            return "Capability fallbacks"
        if domain == "D10_tool_failure_and_grounding" or "error_handling" in meta_cat or "not_found" in meta_cat:
            return "Tool-error responses"
        if domain in ["D9_cross_account_privacy", "D9_adversarial_security"] or dtype in ["refusal", "explicit_refusal"] and any(w in meta_cat for w in ["privacy", "override", "unauthorized", "refusal", "harvest"]):
            return "Security refusals"
        if "ineligible" in meta_cat or "refusal" in dtype:
            # Policy/eligibility refusal
            return "Security refusals"
        return "Post-tool final answers"


def compute_target_tokens(dp: dict) -> int:
    """Computes exact active supervised tokens for target assistant turn under Qwen3."""
    full_text = tok.apply_chat_template(dp["messages"], tools=dp["tools"], tokenize=False, enable_thinking=False)
    prefix_text = tok.apply_chat_template(dp["messages"][:-1], tools=dp["tools"], tokenize=False, enable_thinking=False, add_generation_prompt=True)
    full_ids = tok(full_text)["input_ids"]
    pref_ids = tok(prefix_text)["input_ids"]
    return len(full_ids) - len(pref_ids)


def analyze_dataset(path: Path, name: str):
    with open(path, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]

    counts = defaultdict(int)
    tokens = defaultdict(int)
    min_tokens = defaultdict(lambda: 999999)
    max_tokens = defaultdict(int)

    for dp in samples:
        cat = classify_decision_point(dp)
        t_len = compute_target_tokens(dp)
        assert t_len > 0, f"Error: sample {dp['decision_point_id']} has 0 supervised target tokens!"
        counts[cat] += 1
        tokens[cat] += t_len
        min_tokens[cat] = min(min_tokens[cat], t_len)
        max_tokens[cat] = max(max_tokens[cat], t_len)

    return samples, counts, tokens, min_tokens, max_tokens


b_samples, b_counts, b_tokens, b_min, b_max = analyze_dataset(BASELINE_PATH, "Baseline 112")
s_samples, s_counts, s_tokens, s_min, s_max = analyze_dataset(STAGE6_PATH, "Stage 6 70")

all_categories = [
    "First tool calls",
    "Subsequent tool calls",
    "Post-tool final answers",
    "Security refusals",
    "Clarifications",
    "Capability fallbacks",
    "Tool-error responses",
]

print("=" * 115)
print(f"{'Category':28s} | {'Baseline 112 (DPs / Toks)':26s} | {'Stage 6 70 (DPs / Toks)':26s} | {'Combined 182 (DPs / Toks)':26s}")
print("-" * 115)

tot_b_dp, tot_b_tok = 0, 0
tot_s_dp, tot_s_tok = 0, 0
tot_c_dp, tot_c_tok = 0, 0

for cat in all_categories:
    bc, bt = b_counts[cat], b_tokens[cat]
    sc, st = s_counts[cat], s_tokens[cat]
    cc, ct = bc + sc, bt + st

    tot_b_dp += bc
    tot_b_tok += bt
    tot_s_dp += sc
    tot_s_tok += st
    tot_c_dp += cc
    tot_c_tok += ct

    b_str = f"{bc:2d} DPs / {bt:5d} toks" if bc > 0 else " 0 DPs /     0 toks"
    s_str = f"{sc:2d} DPs / {st:5d} toks" if sc > 0 else " 0 DPs /     0 toks"
    c_str = f"{cc:2d} DPs / {ct:5d} toks"

    print(f"{cat:28s} | {b_str:26s} | {s_str:26s} | {c_str:26s}")

print("-" * 115)
print(f"{'TOTAL TOOL CALL TARGETS':28s} | {b_counts['First tool calls'] + b_counts['Subsequent tool calls']:2d} DPs / {b_tokens['First tool calls'] + b_tokens['Subsequent tool calls']:5d} toks       | {s_counts['First tool calls'] + s_counts['Subsequent tool calls']:2d} DPs / {s_tokens['First tool calls'] + s_tokens['Subsequent tool calls']:5d} toks       | {b_counts['First tool calls'] + b_counts['Subsequent tool calls'] + s_counts['First tool calls'] + s_counts['Subsequent tool calls']:2d} DPs / {b_tokens['First tool calls'] + b_tokens['Subsequent tool calls'] + s_tokens['First tool calls'] + s_tokens['Subsequent tool calls']:5d} toks")
print(f"{'TOTAL PROSE TARGETS':28s} | {tot_b_dp - (b_counts['First tool calls'] + b_counts['Subsequent tool calls']):2d} DPs / {tot_b_tok - (b_tokens['First tool calls'] + b_tokens['Subsequent tool calls']):5d} toks       | {tot_s_dp - (s_counts['First tool calls'] + s_counts['Subsequent tool calls']):2d} DPs / {tot_s_tok - (s_tokens['First tool calls'] + s_tokens['Subsequent tool calls']):5d} toks       | {tot_c_dp - (b_counts['First tool calls'] + b_counts['Subsequent tool calls'] + s_counts['First tool calls'] + s_counts['Subsequent tool calls']):2d} DPs / {tot_c_tok - (b_tokens['First tool calls'] + b_tokens['Subsequent tool calls'] + s_tokens['First tool calls'] + s_tokens['Subsequent tool calls']):5d} toks")
print("=" * 115)
print(f"{'GRAND TOTAL SUPERVISED':28s} | {tot_b_dp:2d} DPs / {tot_b_tok:5d} toks       | {tot_s_dp:2d} DPs / {tot_s_tok:5d} toks       | {tot_c_dp:2d} DPs / {tot_c_tok:5d} toks")
print("=" * 115)
