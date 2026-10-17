"""
Prompt Optimization & Cost Reduction Analysis Script.

Compares v1.0 (baseline) vs v1.1_trimmed (compressed) prompt tokens,
calculates empirical cost savings using the Runwise cost model,
and prints a formatted Markdown report.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from runwise.agent.loop import _load_system_prompt
from runwise.service.cost import calculate_cost_breakdown, format_cost_table


def main() -> None:
    prompt_v1_0 = _load_system_prompt("v1.0")
    prompt_v1_1 = _load_system_prompt("v1.1_trimmed")

    chars_base = len(prompt_v1_0)
    chars_opt = len(prompt_v1_1)
    char_reduction = (chars_base - chars_opt) / chars_base * 100

    # LiteLLM/Gemini rough token estimation: ~4 chars per token
    base_prompt_tokens = round(chars_base / 3.8) + 150  # including tools & system framing
    opt_prompt_tokens = round(chars_opt / 3.8) + 150
    completion_tokens = 60  # average customer turn output

    b_base = calculate_cost_breakdown(
        model="gemini-2.5-flash",
        prompt_tokens=base_prompt_tokens,
        completion_tokens=completion_tokens,
    )
    b_opt = calculate_cost_breakdown(
        model="gemini-2.5-flash",
        prompt_tokens=opt_prompt_tokens,
        completion_tokens=completion_tokens,
    )

    token_delta_pct = (b_opt.prompt_tokens - b_base.prompt_tokens) / b_base.prompt_tokens * 100
    cost_delta_pct = (b_opt.total_cost_usd - b_base.total_cost_usd) / b_base.total_cost_usd * 100
    annual_savings_100k = (b_base.projected_monthly_100k_daily - b_opt.projected_monthly_100k_daily) * 12

    print("\n" + "=" * 75)
    print("  🚀 RUNWISE PROMPT OPTIMIZATION & COST EXPERIMENT REPORT")
    print("=" * 75)
    print(f"  • Baseline Prompt (v1.0):         {chars_base:,} chars (~{base_prompt_tokens:,} input tokens)")
    print(f"  • Optimized Prompt (v1.1_trimmed): {chars_opt:,} chars (~{opt_prompt_tokens:,} input tokens)")
    print(f"  • Prompt Character Reduction:      -{char_reduction:.1f}%")
    print(f"  • Total Request Cost Reduction:    {cost_delta_pct:+.1f}%")
    print(f"  • Projected Annual Savings (100k): ${annual_savings_100k:,.2f} USD")
    print("=" * 75 + "\n")

    table = format_cost_table(b_base, b_opt)
    print(table)
    print("\n")


if __name__ == "__main__":
    main()
