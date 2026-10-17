"""
Comparative Baseline Evaluator for Model Auto-Routing.

Audits empirical accuracy, token economics, latency percentiles, and cost per 1k requests
across four routing strategies:
1. Always Cheap (Gemini 2.5 Flash)
2. Always Strong (Gemini 2.5 Pro)
3. Deterministic Rule Router (Inquiries -> Flash, Mutations/Adversarial -> Pro)
4. Cost-Aware Adaptive Semantic Router
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
import sys

from runwise.evals.dataset import load_tasks
from runwise.service.auto_router import AutoRouter, AutoRouterConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Official Vertex AI pricing per 1M tokens
RATES = {
    "flash": {"input": 0.075, "output": 0.300},
    "pro":   {"input": 1.250, "output": 5.000},
}


def load_latest_trajectories(base_dir: Path) -> dict[str, dict]:
    """Finds and parses the newest trajectories.jsonl file under base_dir."""
    pattern = str(base_dir / "run_*" / "trajectories.jsonl")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No trajectory files found matching {pattern}")
    latest_file = sorted(matches)[-1]
    
    records = {}
    with open(latest_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                records[item["task_id"]] = item
    return records


def calculate_metrics(records: list[dict], model_type: str) -> dict:
    rates = RATES[model_type]
    count = len(records)
    prompt_tokens = sum(r["usage"]["prompt_tokens"] for r in records)
    comp_tokens = sum(r["usage"]["completion_tokens"] for r in records)
    total_tokens = prompt_tokens + comp_tokens
    
    cost = (prompt_tokens * rates["input"] + comp_tokens * rates["output"]) / 1_000_000.0
    cost_per_1k = (cost / count) * 1000.0 if count else 0.0
    
    latencies = sorted(r["usage"]["latency_ms"] / 1000.0 for r in records)
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    
    successes = sum(1 for r in records if r.get("exit_reason") == "NORMAL_COMPLETION")
    accuracy = (successes / count) * 100.0 if count else 0.0
    
    return {
        "count": count,
        "accuracy": accuracy,
        "prompt_tokens": prompt_tokens,
        "comp_tokens": comp_tokens,
        "total_tokens": total_tokens,
        "total_cost": cost,
        "cost_per_1k": cost_per_1k,
        "p50_sec": p50,
        "p95_sec": p95,
    }


def main() -> None:
    cheap_dir = PROJECT_ROOT / "results" / "routing" / "baseline_cheap"
    strong_dir = PROJECT_ROOT / "results" / "routing" / "baseline_strong"
    
    flash_runs = load_latest_trajectories(cheap_dir)
    pro_runs = load_latest_trajectories(strong_dir)
    
    tasks = {t.id: t for t in load_tasks(split="dev")}
    task_ids = sorted(list(flash_runs.keys()))
    count = len(task_ids)
    
    # 1. Baseline 1: Always Cheap (Flash)
    m_flash = calculate_metrics(list(flash_runs.values()), "flash")
    
    # 2. Baseline 2: Always Strong (Pro)
    m_pro = calculate_metrics(list(pro_runs.values()), "pro")
    
    # 3. Baseline 3: Deterministic Rule Router (inquiry -> Flash, others -> Pro)
    rule_total_cost = 0.0
    rule_latencies = []
    rule_successes = 0
    rule_prompt_tokens = 0
    rule_comp_tokens = 0
    
    for tid in task_ids:
        r_f = flash_runs[tid]
        r_p = pro_runs[tid]
        
        is_inquiry = "inq" in tid
        chosen_record = r_f if is_inquiry else r_p
        chosen_model = "flash" if is_inquiry else "pro"
        
        p_in = chosen_record["usage"]["prompt_tokens"]
        p_out = chosen_record["usage"]["completion_tokens"]
        rates = RATES[chosen_model]
        
        cost = (p_in * rates["input"] + p_out * rates["output"]) / 1_000_000.0
        rule_total_cost += cost
        rule_prompt_tokens += p_in
        rule_comp_tokens += p_out
        rule_latencies.append(chosen_record["usage"]["latency_ms"] / 1000.0)
        if chosen_record.get("exit_reason") == "NORMAL_COMPLETION":
            rule_successes += 1

    rule_latencies.sort()
    m_rule = {
        "count": count,
        "accuracy": (rule_successes / count) * 100.0,
        "prompt_tokens": rule_prompt_tokens,
        "comp_tokens": rule_comp_tokens,
        "total_tokens": rule_prompt_tokens + rule_comp_tokens,
        "total_cost": rule_total_cost,
        "cost_per_1k": (rule_total_cost / count) * 1000.0,
        "p50_sec": rule_latencies[len(rule_latencies) // 2],
        "p95_sec": rule_latencies[int(len(rule_latencies) * 0.95)],
    }

    # 4. Strategy 4: Adaptive Semantic Router
    router = AutoRouter(AutoRouterConfig(complexity_threshold=0.45))
    adaptive_total_cost = 0.0
    adaptive_latencies = []
    adaptive_successes = 0
    adaptive_prompt_tokens = 0
    adaptive_comp_tokens = 0
    flash_routed_count = 0
    pro_routed_count = 0
    
    for tid in task_ids:
        task_obj = tasks[tid]
        decision = router.route(task_obj.user_prompt)
        
        is_flash = "flash" in decision.selected_model
        if is_flash:
            flash_routed_count += 1
            chosen_record = flash_runs[tid]
            chosen_model = "flash"
        else:
            pro_routed_count += 1
            chosen_record = pro_runs[tid]
            chosen_model = "pro"
            
        p_in = chosen_record["usage"]["prompt_tokens"]
        p_out = chosen_record["usage"]["completion_tokens"]
        rates = RATES[chosen_model]
        
        cost = (p_in * rates["input"] + p_out * rates["output"]) / 1_000_000.0
        adaptive_total_cost += cost
        adaptive_prompt_tokens += p_in
        adaptive_comp_tokens += p_out
        adaptive_latencies.append(chosen_record["usage"]["latency_ms"] / 1000.0)
        if chosen_record.get("exit_reason") == "NORMAL_COMPLETION":
            adaptive_successes += 1

    adaptive_latencies.sort()
    m_adaptive = {
        "count": count,
        "accuracy": (adaptive_successes / count) * 100.0,
        "prompt_tokens": adaptive_prompt_tokens,
        "comp_tokens": adaptive_comp_tokens,
        "total_tokens": adaptive_prompt_tokens + adaptive_comp_tokens,
        "total_cost": adaptive_total_cost,
        "cost_per_1k": (adaptive_total_cost / count) * 1000.0,
        "p50_sec": adaptive_latencies[len(adaptive_latencies) // 2],
        "p95_sec": adaptive_latencies[int(len(adaptive_latencies) * 0.95)],
    }

    # Render Comparative Matrix
    print("\n" + "=" * 92)
    print("  📊 MODEL AUTO-ROUTING BENCHMARK COMPARISON (35 Dev Tasks)")
    print("=" * 92)
    header = f"{'Routing Strategy':<28} | {'Pass Rate':<10} | {'Cost / 1k':<12} | {'p50 Latency':<12} | {'p95 Latency':<12}"
    print(header)
    print("-" * 92)
    
    strategies = [
        ("1. Always Cheap (Flash)", m_flash),
        ("2. Always Strong (Pro)", m_pro),
        ("3. Rule-Based Router", m_rule),
        ("4. Adaptive Semantic Router", m_adaptive),
    ]
    for name, m in strategies:
        print(f"{name:<28} | {m['accuracy']:>8.1f}% | ${m['cost_per_1k']:>10.4f} | {m['p50_sec']:>10.2f}s | {m['p95_sec']:>10.2f}s")
        
    print("=" * 92)
    savings_vs_pro = ((m_pro["cost_per_1k"] - m_adaptive["cost_per_1k"]) / m_pro["cost_per_1k"]) * 100.0
    savings_vs_rule = ((m_rule["cost_per_1k"] - m_adaptive["cost_per_1k"]) / m_rule["cost_per_1k"]) * 100.0
    flash_pct = (flash_routed_count / count) * 100.0
    pro_pct = (pro_routed_count / count) * 100.0
    print(f"  • Traffic Distribution:     {flash_routed_count}/{count} Flash ({flash_pct:.1f}%), {pro_routed_count}/{count} Pro ({pro_pct:.1f}%)")
    print(f"  • Cost Savings vs Strong:   -{savings_vs_pro:.1f}% (slashed from ${m_pro['cost_per_1k']:.2f} to ${m_adaptive['cost_per_1k']:.2f} / 1k)")
    print(f"  • Cost Savings vs Rule:     -{savings_vs_rule:.1f}% (slashed from ${m_rule['cost_per_1k']:.2f} to ${m_adaptive['cost_per_1k']:.2f} / 1k)")
    print(f"  • Latency Improvement:      {m_adaptive['p50_sec']:.2f}s p50 (vs {m_pro['p50_sec']:.2f}s Pro / {m_rule['p50_sec']:.2f}s Rule)")
    print("=" * 92 + "\n")


if __name__ == "__main__":
    main()
