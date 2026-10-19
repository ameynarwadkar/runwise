"""
Stage 4: Execution script for the 8 Harder Reasoning Diagnostic Benchmark Scenarios.
Executes paired Gemini 2.5 Flash vs Gemini 2.5 Pro evaluations on isolated SQLite sandboxes.
Saves results into results/routing/hard_reasoning/ with incremental persistence and strict budget guards.
"""

from __future__ import annotations

import json
from pathlib import Path

from runwise.evals.hard_reasoning_generator import generate_8_hard_reasoning_scenarios
from runwise.evals.pilot_runner import run_paired_pilot

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "results" / "routing" / "hard_reasoning"
BUDGET_CEILING_USD = 0.15


def main() -> None:
    print("=" * 70)
    print("STAGE 4: HARDER REASONING DIAGNOSTIC BENCHMARK (FLASH VS PRO)")
    print(f"Target Directory: {OUTPUT_DIR}")
    print(f"Budget Limit: ${BUDGET_CEILING_USD:.2f} USD")
    print("=" * 70)

    scenarios = generate_8_hard_reasoning_scenarios()
    print(f"Loaded {len(scenarios)} hard reasoning scenarios:")
    for s in scenarios:
        print(f"  - [{s.task_id}] {s.family_id} ({s.category})")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = run_paired_pilot(
        scenarios=scenarios,
        approved_by_user=True,
        budget_limit_usd=BUDGET_CEILING_USD,
        repeat_task_ids=[],
        output_dir=OUTPUT_DIR,
        resume_from_disk=True,
    )

    summary_file = OUTPUT_DIR / "summary.json"
    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print("STAGE 4 BENCHMARK COMPLETED SUCCESSFULLY")
    print(f"Total Spent: ${summary.get('measured_usage', {}).get('total_pilot_cost_usd', 0.0):.4f} USD")
    print(f"Flash Pass Rate: {summary['flash_pass_rate']:.1%}")
    print(f"Pro Pass Rate: {summary['pro_pass_rate']:.1%}")
    print(f"Disagreement Rate: {summary['disagreement_rate']:.1%}")
    print(f"Outcome Distribution: {summary['outcome_distribution']}")
    print(f"Summary JSON saved to: {summary_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
