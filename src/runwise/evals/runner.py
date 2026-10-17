"""
Parallel Evaluation Runner and Benchmark Orchestrator.

Executes evaluation suites against isolated ephemeral SQLite sandboxes:
- Controlled concurrency across thread worker pool
- Per-trial sandbox isolation and frozen deterministic clock injection
- Full trajectory logging to JSONL and statistical summary output
- CLI entrypoint for running evaluations.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import os
import sys
from pathlib import Path
import threading
from typing import Any
import uuid

# Load credentials from .env into os.environ before agent/litellm imports
from dotenv import load_dotenv
load_dotenv()

from runwise.config import get_provider_config
from runwise.observability.tracer import setup_phoenix_tracer, shutdown_phoenix_tracer
from runwise.agent.loop import AgentLoop
from runwise.agent.trajectory import Trajectory
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext
from runwise.evals.dataset import load_tasks
from runwise.evals.graders.aggregation import evaluate_trial
from runwise.evals.models import Task, TrialOutcome
from runwise.evals.stats import (
    EvaluationSummary,
    TrialRecord,
    compute_evaluation_summary,
)

# Standard paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results" / "runs"


def run_single_trial(
    task: Task,
    trial_idx: int,
    model: str | None = None,
    temperature: float = 0.0,
    max_steps: int = 10,
    mock_completions: list[Any] | None = None,
    mock_judge_response: str | None = None,
) -> tuple[TrialRecord, Trajectory]:
    """
    Executes a single trial in complete database isolation.

    1. Boots ephemeral SQLite in-memory sandbox.
    2. Injects deterministic clock and session context.
    3. Runs AgentLoop.
    4. Evaluates trial across Layered Graders (Tiers 1–4).
    5. Tears down the sandbox.
    """
    cfg = get_provider_config(override_model=model)
    resolved_model = cfg.model_identifier
    trial_id = f"{task.id}_tr{trial_idx}"
    conn = SandboxDB.create_connection()

    try:
        session = SessionContext(
            conn=conn,
            trial_id=trial_id,
            current_time_iso=task.injected_clock_iso,
            authenticated_user_id=None,
        )

        agent = AgentLoop(
            model=resolved_model,
            temperature=temperature,
            max_steps=max_steps,
        )

        trajectory = agent.run(
            user_prompt=task.user_prompt,
            session=session,
            task_id=task.id,
            mock_completions=mock_completions,
        )

        outcome, _ = evaluate_trial(
            trajectory=trajectory,
            task=task,
            conn=conn,
            mock_judge_response=mock_judge_response,
        )

        record = TrialRecord(
            task_id=task.id,
            trial_id=trial_id,
            category=task.category,
            difficulty=task.difficulty,
            split=task.split,
            outcome=outcome,
            latency_ms=trajectory.usage.latency_ms,
            total_tokens=trajectory.usage.total_tokens,
        )

        return record, trajectory

    finally:
        conn.close()


class EvaluationRunner:
    """
    Orchestrates parallel multi-trial benchmarks and generates evaluation artifacts.
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.0,
        n_trials: int = 1,
        workers: int = 4,
        results_dir: Path | str = DEFAULT_RESULTS_DIR,
        mock_completions_map: dict[str, list[Any]] | None = None,
    ):
        cfg = get_provider_config(override_model=model)
        self.model = cfg.model_identifier 
        self.temperature = temperature
        self.n_trials = n_trials
        self.workers = workers
        self.results_dir = Path(results_dir)
        self.mock_completions_map = mock_completions_map or {}
        self._file_lock = threading.Lock()

    def run(self, tasks: list[Task]) -> tuple[EvaluationSummary, Path]:
        """
        Runs the benchmark across all tasks in parallel.
        Writes results to results/runs/<run_id>/.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"run_{timestamp}_{uuid.uuid4().hex[:6]}"
        run_dir = self.results_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        traj_file = run_dir / "trajectories.jsonl"
        records: list[TrialRecord] = []

        # Create trial execution queue
        work_items: list[tuple[Task, int]] = []
        for task in tasks:
            for i in range(1, self.n_trials + 1):
                work_items.append((task, i))

        print(f"\n🚀 Starting Run: {run_id}", flush=True)
        print(f"📊 Tasks: {len(tasks)} | Trials/Task: {self.n_trials} | Total Trials: {len(work_items)} | Workers: {self.workers}\n", flush=True)

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_item = {
                executor.submit(
                    run_single_trial,
                    task=task,
                    trial_idx=idx,
                    model=self.model,
                    temperature=self.temperature,
                    mock_completions=self.mock_completions_map.get(task.id),
                ): (task, idx)
                for task, idx in work_items
            }

            completed_count = 0
            for future in as_completed(future_to_item):
                task, idx = future_to_item[future]
                completed_count += 1
                try:
                    record, trajectory = future.result()
                    records.append(record)

                    # Thread-safe write to trajectories.jsonl
                    with self._file_lock:
                        with open(traj_file, "a", encoding="utf-8") as f:
                            f.write(trajectory.model_dump_json() + "\n")

                    status_sym = "✅" if record.outcome == TrialOutcome.PASS else "❌"
                    print(f"  [{completed_count:3d}/{len(work_items):3d}] {status_sym} {task.id} (trial {idx}) -> {record.outcome.value}", flush=True)

                except Exception as exc:
                    print(f"  [{completed_count:3d}/{len(work_items):3d}] ⚠️  {task.id} (trial {idx}) FAILED with exception: {exc}", flush=True)

        # Compute benchmark summary
        summary = compute_evaluation_summary(records, k_values=[1, 2, 4])

        # Save summary report JSON
        summary_path = run_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary.model_dump_json(indent=2))

        self._print_terminal_report(summary, run_id, run_dir)
        return summary, run_dir

    def _print_terminal_report(self, summary: EvaluationSummary, run_id: str, run_dir: Path) -> None:
        """Renders an ASCII summary table for the terminal."""
        pct = summary.overall_success_rate * 100
        print("\n" + "=" * 65)
        print(f"  🏆 BENCHMARK EVALUATION REPORT — {run_id}")
        print("=" * 65)
        print(f"  Total Tasks:  {summary.total_tasks}")
        print(f"  Total Trials: {summary.total_trials}")
        print(f"  Overall Pass Rate: {pct:.1f}%")
        print("-" * 65)
        print("  RELIABILITY METRICS:")
        for k, v in summary.pass_hat_k.items():
            print(f"    • pass^{k} (consensus reliability): {v * 100:.1f}%")
        for k, v in summary.pass_at_k.items():
            print(f"    • pass@{k} (exploration rate):      {v * 100:.1f}%")
        print("-" * 65)
        print("  CATEGORY BREAKDOWN:")
        for cat, rate in summary.category_success_rates.items():
            print(f"    • {cat:<18}: {rate * 100:.1f}%")
        print("-" * 65)
        print("  DIFFICULTY BREAKDOWN:")
        for diff, rate in summary.difficulty_success_rates.items():
            print(f"    • {diff:<18}: {rate * 100:.1f}%")
        print("=" * 65)
        print(f"  📁 Artifacts saved to: {run_dir}\n")


def main() -> None:
    """CLI Entrypoint for running evaluations."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    phoenix_active = setup_phoenix_tracer()
    default_model = get_provider_config().model_identifier
    parser = argparse.ArgumentParser(description="Runwise Customer Support Agent Evaluation Harness")
    parser.add_argument("--split", choices=["all", "dev", "frozen_holdout"], default="dev", help="Dataset split to evaluate")
    parser.add_argument("--trials", type=int, default=1, help="Number of trials per task (n)")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent worker threads")
    parser.add_argument("--model", type=str, default=default_model, help="LiteLLM model identifier")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tasks for quick testing")
    args = parser.parse_args()

    split_filter = None if args.split == "all" else args.split
    tasks = load_tasks(split=split_filter)

    if args.limit:
        tasks = tasks[:args.limit]

    runner = EvaluationRunner(
        model=args.model,
        n_trials=args.trials,
        workers=args.workers,
    )
    runner.run(tasks)
    if phoenix_active:
        from opentelemetry import trace
        tp = trace.get_tracer_provider()
        if hasattr(tp, "force_flush"):
            tp.force_flush()

        print("🔭 Phoenix UI active at: http://localhost:6006")
        print("👉 Press Ctrl+C in this terminal to shut down Phoenix server and exit...\n")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down Phoenix server...\n")
        finally:
            shutdown_phoenix_tracer()

if __name__ == "__main__":
    main()
