import json
from transformers import AutoTokenizer

try:
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B", local_files_only=True)
except Exception:
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")

with open("data/sft/decision_points_stage6_70_examples.jsonl", encoding="utf-8") as f:
    dps = [json.loads(line) for line in f if line.strip()]

target_lens = []
full_lens = []

for dp in dps:
    full_text = tok.apply_chat_template(dp["messages"], tools=dp["tools"], tokenize=False, enable_thinking=False)
    prefix_text = tok.apply_chat_template(dp["messages"][:-1], tools=dp["tools"], tokenize=False, enable_thinking=False, add_generation_prompt=True)
    
    full_toks = tok(full_text)["input_ids"]
    pref_toks = tok(prefix_text)["input_ids"]
    
    target_toks_len = len(full_toks) - len(pref_toks)
    target_lens.append(target_toks_len)
    full_lens.append(len(full_toks))

print(f"Total Stage 6 Decision Points: {len(dps)}")
print(f"Average Full Context Length:   {sum(full_lens)/len(full_lens):.1f} tokens (min={min(full_lens)}, max={max(full_lens)})")
print(f"Total Supervised Target Mass:  {sum(target_lens)} tokens")
print(f"Average Active Tokens/DP:      {sum(target_lens)/len(target_lens):.1f} tokens (min={min(target_lens)}, max={max(target_lens)})")
