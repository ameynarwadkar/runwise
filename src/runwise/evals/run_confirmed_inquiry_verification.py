"""
Minimal 4-call live verification runner for rw_pilot_0025 and rw_pilot_0026.
Evaluates Gemini 2.5 Flash and Gemini 2.5 Pro against the new trusted financial authorization boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

from runwise.evals.pilot_generator import generate_30_scenario_pilot
from runwise.evals.pilot_runner import run_paired_pilot

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "results" / "routing" / "pilot_confirmed_inquiries"


def run_live_verification() -> dict:
    pool = generate_30_scenario_pilot()
    target_tasks = ["rw_pilot_0025", "rw_pilot_0026"]
    scenarios = [s for s in pool if s.task_id in target_tasks]

    print(f"Targeting {len(scenarios)} scenarios for live verification: {[s.task_id for s in scenarios]}")
    print(f"Writing outputs to isolated directory: {OUTPUT_DIR}")

    summary = run_paired_pilot(
        scenarios=scenarios,
        approved_by_user=True,
        budget_limit_usd=0.05,
        repeat_task_ids=[],
        repeat_trials=0,
        output_dir=OUTPUT_DIR,
    )
    return summary


if __name__ == "__main__":
    summary = run_live_verification()
    print("\n--- Live Verification Summary ---")
    print(json.dumps(summary, indent=2))
