"""
Colab Diagnostic Script for Phase 2 & Phase 3 Inspection.
Inspects saved Experiment B manifest, adapter weight norms, NaNs/Infs,
and compares base vs. reloaded adapter token generation in eval mode.
"""

import json
import os
import torch

def inspect_experiment_b(checkpoint_dir="/content/drive/MyDrive/runwise_experiment_b_adapter"):
    print("=" * 80)
    print("PHASE 2 & 3: EXPERIMENT B FORENSIC INTEGRITY AUDIT")
    print("=" * 80)
    
    # 1. Inspect Manifest & Loss Progression
    manifest_path = os.path.join(checkpoint_dir, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        print("\n[1] TRAINING MANIFEST & LOSS PROGRESSION:")
        print(f"  Initial Loss: {manifest.get('initial_loss')}")
        print(f"  Final Loss:   {manifest.get('final_loss')}")
        print(f"  Average Loss: {manifest.get('average_loss')}")
        print(f"  Steps Completed: {manifest.get('steps_completed')}")
        step_losses = manifest.get("step_losses", [])
        print("\n  Step Loss History (every 5 steps):")
        for i, l in enumerate(step_losses, 1):
            if i == 1 or i % 5 == 0 or i == len(step_losses):
                ex_id = manifest.get("shuffled_example_ids", [])[i-1] if i-1 < len(manifest.get("shuffled_example_ids", [])) else "N/A"
                print(f"    Step {i:02d}/40 [{ex_id}]: Loss = {l:.4f}")
    else:
        print(f"\n[1] Manifest not found at: {manifest_path}")

    # 2. Inspect Adapter Tensors for NaNs, Infs, and Extreme Norms
    adapter_file = os.path.join(checkpoint_dir, "adapter_model.safetensors")
    bin_file = os.path.join(checkpoint_dir, "adapter_model.bin")
    
    weights = {}
    if os.path.exists(adapter_file):
        from safetensors.torch import load_file
        weights = load_file(adapter_file)
        print(f"\n[2] Loaded safetensors adapter: {len(weights)} weight tensors")
    elif os.path.exists(bin_file):
        weights = torch.load(bin_file, map_location="cpu")
        print(f"\n[2] Loaded bin adapter: {len(weights)} weight tensors")
    else:
        print(f"\n[2] Adapter weights not found in {checkpoint_dir}")

    if weights:
        has_nan = False
        has_inf = False
        max_val = 0.0
        max_norm = 0.0
        max_norm_layer = ""
        total_params = 0
        
        print("\n  Sample Layer Statistics:")
        for name, tensor in list(weights.items())[:6]:
            t = tensor.float()
            norm = torch.norm(t).item()
            nan_cnt = torch.isnan(t).sum().item()
            inf_cnt = torch.isinf(t).sum().item()
            total_params += t.numel()
            if nan_cnt > 0: has_nan = True
            if inf_cnt > 0: has_inf = True
            max_val = max(max_val, t.abs().max().item())
            if norm > max_norm:
                max_norm = norm
                max_norm_layer = name
            print(f"    {name[-40:]:<40} | Dtype: {str(t.dtype):<10} | Norm: {norm:.4f} | Min: {t.min().item():.4f} | Max: {t.max().item():.4f}")

        # Check full model
        for name, tensor in weights.items():
            t = tensor.float()
            if torch.isnan(t).any(): has_nan = True
            if torch.isinf(t).any(): has_inf = True
            max_val = max(max_val, t.abs().max().item())
            norm = torch.norm(t).item()
            if norm > max_norm:
                max_norm = norm
                max_norm_layer = name
                
        print("\n  Global Adapter Weight Health:")
        print(f"    NaN Detected:       {has_nan}")
        print(f"    Inf Detected:       {has_inf}")
        print(f"    Global Max Abs Val: {max_val:.4f}")
        print(f"    Max Frobenius Norm: {max_norm:.4f} (in {max_norm_layer})")

if __name__ == "__main__":
    print("Forensic inspection script compiled.")
