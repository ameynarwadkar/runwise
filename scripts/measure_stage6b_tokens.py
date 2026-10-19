import json
from transformers import AutoTokenizer

try:
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B", local_files_only=True)
except Exception:
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")

print("=" * 80)
print("AUDIT: 14 TARGETED STAGE 6B DECISION POINTS")
print("=" * 80)

with open("data/sft/decision_points_stage6b_14_examples.jsonl", encoding="utf-8") as f:
    dps_14 = [json.loads(line) for line in f if line.strip()]

target_lens_14 = []
full_lens_14 = []

print(f"{'DP ID':22s} | {'Category':20s} | {'Decision Type':18s} | {'Target Toks':11s} | {'Full Toks':9s}")
print("-" * 90)

for dp in dps_14:
    full_text = tok.apply_chat_template(dp["messages"], tools=dp["tools"], tokenize=False, enable_thinking=False)
    prefix_text = tok.apply_chat_template(dp["messages"][:-1], tools=dp["tools"], tokenize=False, enable_thinking=False, add_generation_prompt=True)
    
    full_toks = tok(full_text)["input_ids"]
    pref_toks = tok(prefix_text)["input_ids"]
    
    target_toks_len = len(full_toks) - len(pref_toks)
    target_lens_14.append(target_toks_len)
    full_lens_14.append(len(full_toks))

    print(f"{dp['decision_point_id']:22s} | {dp['curriculum_domain']:20s} | {dp['decision_type']:18s} | {target_toks_len:11d} | {len(full_toks):9d}")

print("-" * 90)
print(f"Total 14-DP Target Supervised Tokens: {sum(target_lens_14)}")
print(f"Average Active Target Tokens / DP:   {sum(target_lens_14)/len(target_lens_14):.1f} (min={min(target_lens_14)}, max={max(target_lens_14)})")
print(f"Average Full Context Length:         {sum(full_lens_14)/len(full_lens_14):.1f} (min={min(full_lens_14)}, max={max(full_lens_14)})")

print("\n" + "=" * 80)
print("AUDIT: FULL 196 COMBINED DECISION POINTS (EXPERIMENT G CANDIDATE)")
print("=" * 80)

with open("data/sft/decision_points_combined_196_examples.jsonl", encoding="utf-8") as f:
    dps_196 = [json.loads(line) for line in f if line.strip()]

target_lens_196 = []
full_lens_196 = []
decision_types = {}

for dp in dps_196:
    full_text = tok.apply_chat_template(dp["messages"], tools=dp["tools"], tokenize=False, enable_thinking=False)
    prefix_text = tok.apply_chat_template(dp["messages"][:-1], tools=dp["tools"], tokenize=False, enable_thinking=False, add_generation_prompt=True)
    
    full_toks = tok(full_text)["input_ids"]
    pref_toks = tok(prefix_text)["input_ids"]
    
    target_toks_len = len(full_toks) - len(pref_toks)
    target_lens_196.append(target_toks_len)
    full_lens_196.append(len(full_toks))

    dt = dp.get("decision_type", "unknown")
    if dt not in decision_types:
        decision_types[dt] = {"count": 0, "tokens": 0}
    decision_types[dt]["count"] += 1
    decision_types[dt]["tokens"] += target_toks_len

print(f"Total Decision Points:        {len(dps_196)}")
print(f"Total Supervised Target Mass: {sum(target_lens_196)} tokens")
print(f"Average Active Tokens/DP:     {sum(target_lens_196)/len(target_lens_196):.1f} tokens")
print(f"Average Full Context Tokens:  {sum(full_lens_196)/len(full_lens_196):.1f} tokens")
print("\nSupervision Breakdown by Decision Type:")
print(f"{'Decision Type':25s} | {'Count':6s} | {'Total Tokens':12s} | {'Avg Toks/DP':11s}")
print("-" * 62)
for dt, stats in sorted(decision_types.items(), key=lambda x: -x[1]["tokens"]):
    avg_t = stats["tokens"] / stats["count"]
    print(f"{dt:25s} | {stats['count']:6d} | {stats['tokens']:12d} | {avg_t:11.1f}")
