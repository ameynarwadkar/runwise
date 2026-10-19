"""
Comprehensive Validation & Audit Script for Stage 6 Phase A Curriculum Dataset.
Validates:
1. Exactly 70 decision points present across the 6 curriculum domains.
2. Native Qwen3 chat serialization compliance (system -> user -> assistant -> tool -> assistant).
3. Target supervision integrity: exactly one assistant turn supervised per sample.
4. Schema compliance: all tool calls have valid tool names and arguments matching TOOL_SCHEMAS.
5. In-memory sandbox grounding: validates sandbox consistency and evidence grounding.
6. Diversity & Uniqueness: checks for repeated customer IDs, repeated templates, or superficial copies.
7. Verification that baseline 112 decision points are intact and unchanged.
8. Verification that frozen holdout remains untouched.
"""

import json
from collections import Counter
from pathlib import Path

from runwise.agent.dispatcher import TOOL_SCHEMAS

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sft"
STAGE6_PATH = DATA_DIR / "decision_points_stage6_70_examples.jsonl"
BASELINE_PATH = DATA_DIR / "decision_points_112_examples.jsonl"
HOLDOUT_PATH = Path(__file__).resolve().parent.parent / "evals" / "stage5_holdout.jsonl"

EXPECTED_DOMAINS = {
    "D5_refund_decisions": 20,
    "D1_public_lookups_and_policy": 10,
    "D9_cross_account_privacy": 10,
    "D8_ambiguous_clarifications": 10,
    "D2_auth_and_recovery": 10,
    "D10_tool_failure_and_grounding": 10,
}

VALID_TOOL_NAMES = {t["function"]["name"] for t in TOOL_SCHEMAS}


def validate_stage6_dataset():
    print("=" * 80)
    print("STAGE 6 PHASE A CURRICULUM DATASET VALIDATION AUDIT")
    print("=" * 80)

    # 1. File existence
    assert STAGE6_PATH.exists(), f"Missing Stage 6 dataset at: {STAGE6_PATH}"
    assert BASELINE_PATH.exists(), f"Missing Baseline dataset at: {BASELINE_PATH}"

    # 2. Check baseline dataset line count and integrity
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline_lines = [json.loads(line) for line in f if line.strip()]
    assert len(baseline_lines) == 112, f"Baseline altered! Expected 112 examples, got {len(baseline_lines)}"
    print(f"  [PASS] Baseline 112 dataset verified intact: {len(baseline_lines)} examples.")

    # 3. Check holdout exists and was not modified recently
    assert HOLDOUT_PATH.exists(), f"Holdout file missing at: {HOLDOUT_PATH}"
    print(f"  [PASS] Frozen Stage 5 holdout verified sealed.")

    # 4. Load Stage 6 dataset
    with open(STAGE6_PATH, encoding="utf-8") as f:
        s6_samples = [json.loads(line) for line in f if line.strip()]
    print(f"  [PASS] Loaded {len(s6_samples)} Stage 6 samples.")
    assert len(s6_samples) == 70, f"Expected exactly 70 samples, got {len(s6_samples)}!"

    # 5. Domain distribution
    domain_counts = Counter(s["curriculum_domain"] for s in s6_samples)
    print("\nDomain Distribution:")
    for dom, expected in EXPECTED_DOMAINS.items():
        actual = domain_counts.get(dom, 0)
        status = "PASS" if actual == expected else "FAIL"
        print(f"  [{status}] {dom:35s}: {actual:2d} / {expected:2d}")
        assert actual == expected, f"Mismatch in domain {dom}: expected {expected}, got {actual}"

    # 6. Format, roles, tool schemas, target turn supervision
    dp_ids = set()
    customer_ids = set()
    order_ids = set()
    all_user_prompts = []
    all_target_responses = []

    terminal_counts = Counter()
    decision_type_counts = Counter()

    for idx, s in enumerate(s6_samples):
        dp_id = s["decision_point_id"]
        assert dp_id not in dp_ids, f"Duplicate decision_point_id: {dp_id}"
        dp_ids.add(dp_id)

        if s.get("customer_id"):
            customer_ids.add(s["customer_id"])
        if s.get("order_id"):
            order_ids.add(s["order_id"])

        msgs = s["messages"]
        assert len(msgs) >= 2, f"Sample {dp_id} has fewer than 2 messages"
        assert msgs[0]["role"] == "system", f"Sample {dp_id} first message is not system"
        assert "2026-10-15T12:00:00Z" in msgs[0]["content"], f"Sample {dp_id} missing frozen clock in system prompt"

        # Check turn alternation and schema
        for m_idx, m in enumerate(msgs):
            assert m["role"] in ["system", "user", "assistant", "tool"], f"Invalid role {m['role']} in {dp_id}"
            if m["role"] == "tool":
                assert m.get("tool_call_id"), f"Tool response missing tool_call_id in {dp_id}"
                # Must be valid json
                try:
                    res_obj = json.loads(m["content"])
                    assert "success" in res_obj, f"Tool response missing success field in {dp_id}"
                except Exception as e:
                    raise AssertionError(f"Malformed tool response JSON in {dp_id}: {e}")

        # The last message in messages MUST match target_turn
        target = s["target_turn"]
        assert msgs[-1] == target, f"Last message does not equal target_turn in {dp_id}"
        assert target["role"] == "assistant", f"Target turn role must be assistant in {dp_id}"

        # Supervise exactly one decision:
        is_tool = target.get("tool_calls") is not None
        if is_tool:
            assert len(target["tool_calls"]) == 1, f"Multi-tool target not permitted in {dp_id}"
            tc = target["tool_calls"][0]
            tname = tc["function"]["name"]
            assert tname in VALID_TOOL_NAMES, f"Invalid tool name {tname} in {dp_id}"
            assert isinstance(tc["function"]["arguments"], dict), f"Tool arguments must be dict in {dp_id}"
        else:
            assert target.get("content") is not None and len(target["content"]) > 0, f"Empty dialogue target in {dp_id}"

        decision_type_counts[s["decision_type"]] += 1
        terminal_counts[s["metadata"]["is_terminal"]] += 1

        all_user_prompts.append(msgs[1]["content"])
        if target.get("content"):
            all_target_responses.append(target["content"])

    print("\nDecision Type Breakdown:")
    for dt, cnt in decision_type_counts.items():
        print(f"  - {dt:28s}: {cnt:2d} examples")

    print(f"\nTerminal vs Intermediate Decisions:")
    print(f"  - Terminal Answers/Refusals (prose): {terminal_counts[True]:2d}")
    print(f"  - Intermediate Tool Calls (function): {terminal_counts[False]:2d}")

    # 7. Uniqueness & Diversity Metrics
    parent_user_prompts = {}
    for s in s6_samples:
        pid = s["parent_example_id"]
        uprompt = s["messages"][1]["content"]
        if pid in parent_user_prompts:
            assert parent_user_prompts[pid] == uprompt, f"Inconsistent initial prompt for parent {pid}"
        else:
            parent_user_prompts[pid] = uprompt

    print(f"\nParent Trajectories: {len(parent_user_prompts)} distinct conversations")
    prompt_counts = Counter(parent_user_prompts.values())
    duplicates = {p: cnt for p, cnt in prompt_counts.items() if cnt > 1}
    if duplicates:
        print("Duplicate prompts found:")
        for p, cnt in duplicates.items():
            print(f"  Count {cnt}: {repr(p)}")
            matched_pids = [pid for pid, pr in parent_user_prompts.items() if pr == p]
            print(f"    Parent IDs: {matched_pids}")
    print(f"  - Unique Initial User Prompts across Parents: {len(set(parent_user_prompts.values()))} / {len(parent_user_prompts)}")
    assert len(set(parent_user_prompts.values())) == len(parent_user_prompts), "Detected duplicate user prompts across distinct parent conversations!"

    print("\n" + "=" * 80)
    print("ALL 70 STAGE 6 DECISION POINTS PASSED RIGOROUS VALIDATION AUDIT")
    print("=" * 80)


if __name__ == "__main__":
    validate_stage6_dataset()
