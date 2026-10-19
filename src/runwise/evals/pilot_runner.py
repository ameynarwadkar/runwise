"""
Paired pilot benchmark execution harness with strict budget guards and approval controls.
Executes paired Gemini 2.5 Flash vs Gemini 2.5 Pro evaluations on isolated SQLite sandboxes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runwise.agent.loop import AgentLoop, ExitReason
from runwise.agent.trajectory import Trajectory
from runwise.config import get_provider_config
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext
from runwise.evals.graders.aggregation import evaluate_trial
from runwise.evals.models import GraderStatus, Task, TrialOutcome
from runwise.evals.routing_schema import (
    PairedEvaluationOutcome,
    PairedScenario,
    TrialOutcomeRecord,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_PILOT_RESULTS_DIR = PROJECT_ROOT / "results" / "routing" / "pilot"

FLASH_MODEL = "vertex_ai/gemini-2.5-flash"
PRO_MODEL = "vertex_ai/gemini-2.5-pro"

# Pricing per token
FLASH_INPUT_PRICE = 0.075 / 1_000_000
FLASH_OUTPUT_PRICE = 0.300 / 1_000_000
PRO_INPUT_PRICE = 1.250 / 1_000_000
PRO_OUTPUT_PRICE = 5.000 / 1_000_000

# Conservative upper bound cost for single call pre-flight budget check
MAX_ESTIMATED_CALL_COST = 0.012

# Representative scenarios for stochastic repeat variance measurement
STOCHASTIC_REPEAT_TASK_IDS = [
    "rw_bitext_0001",  # Routine order inquiry (easy)
    "rw_b77_0005",     # Negation fee dispute (medium)
    "rw_bitext_0009",  # Valid pending cancellation (medium)
    "rw_pilot_0019",   # Conditional multi-order cancellation (hard)
    "rw_pilot_0028",   # Adversarial prompt injection (hard)
]


class PilotApprovalError(PermissionError):
    """Raised when paid execution is attempted without explicit user approval."""
    pass


class PilotBudgetExceededError(ValueError):
    """Raised when estimated or actual pilot execution exceeds the allowed budget ceiling."""
    pass


def compute_trial_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Computes exact trial cost using official Google Vertex AI rates."""
    if "flash" in model.lower():
        return prompt_tokens * FLASH_INPUT_PRICE + completion_tokens * FLASH_OUTPUT_PRICE
    else:
        return prompt_tokens * PRO_INPUT_PRICE + completion_tokens * PRO_OUTPUT_PRICE


def execute_model_trial(
    task: Task,
    trial_idx: int,
    model: str,
) -> tuple[TrialOutcomeRecord, Trajectory]:
    """
    Executes a single model trial in an ephemeral, freshly seeded SQLite sandbox.
    Does NOT use AutoRouter or gateway fallback; LiteLLM queries the specified model directly.
    """
    conn = SandboxDB.create_connection()
    try:
        session = SessionContext(
            conn=conn,
            trial_id=f"{task.id}_{model.split('/')[-1]}_tr{trial_idx}",
            current_time_iso=task.injected_clock_iso,
            authenticated_user_id=None,
        )
        agent = AgentLoop(
            model=model,
            temperature=0.0,
            max_steps=10,
            prompt_version="v1.0",
        )
        trajectory = agent.run(
            user_prompt=task.user_prompt,
            session=session,
            task_id=task.id,
        )

        p_tokens = trajectory.usage.prompt_tokens or 0
        c_tokens = trajectory.usage.completion_tokens or 0
        latency = trajectory.usage.latency_ms or 0.0
        cost = compute_trial_cost(model, p_tokens, c_tokens)

        # Distinguish provider communications errors from task failures
        if trajectory.exit_reason == ExitReason.PROVIDER_ERROR:
            return TrialOutcomeRecord(
                trials_attempted=1,
                trials_passed=0,
                passed=None,
                tier_failures=["provider_error"],
                latency_ms=round(latency, 2),
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                cost_usd=round(cost, 6),
            ), trajectory

        outcome, grader_results = evaluate_trial(trajectory, task, conn=conn)
        passed = (outcome == TrialOutcome.PASS)
        tier_failures = [r.grader_name for r in grader_results if r.status == GraderStatus.FAIL]

        return TrialOutcomeRecord(
            trials_attempted=1,
            trials_passed=1 if passed else 0,
            passed=passed,
            tier_failures=tier_failures,
            latency_ms=round(latency, 2),
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            cost_usd=round(cost, 6),
        ), trajectory
    finally:
        conn.close()


def run_paired_pilot(
    scenarios: list[PairedScenario],
    approved_by_user: bool = False,
    budget_limit_usd: float = 0.50,
    repeat_task_ids: list[str] | None = None,
    repeat_trials: int = 3,
    output_dir: Path | None = None,
    resume_from_disk: bool = True,
) -> dict[str, Any]:
    """
    Executes paired Flash vs Pro evaluation on isolated SQLite sandboxes.

    HARD SAFETY GATES:
    1. Fails immediately with PilotApprovalError unless approved_by_user is explicitly True.
    2. Runs pre-flight budget check before every billable call and raises PilotBudgetExceededError
       if projected spend exceeds budget_limit_usd ($0.50).
    3. Saves results incrementally so interrupted runs can resume without repeating billable calls.
    """
    if not approved_by_user:
        raise PilotApprovalError(
            "Paid pilot execution blocked: You must obtain explicit user approval before launching "
            "paid Vertex AI evaluations."
        )

    out_dir = output_dir or DEFAULT_PILOT_RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    results_file = out_dir / "pilot_paired_results.jsonl"
    trajectories_file = out_dir / "trajectories.jsonl"
    stochastic_file = out_dir / "stochastic_repeats.jsonl"

    target_repeats = set(repeat_task_ids if repeat_task_ids is not None else STOCHASTIC_REPEAT_TASK_IDS)

    # Initialize environment for Vertex AI
    get_provider_config(override_model=FLASH_MODEL)

    completed_scenarios: dict[str, PairedScenario] = {}
    total_spent_usd = 0.0

    # 1. Load existing results if resuming from disk
    if resume_from_disk and results_file.exists():
        for line in results_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                loaded = PairedScenario.model_validate_json(line)
                completed_scenarios[loaded.task_id] = loaded
                f_cost = loaded.paired_eval.flash.cost_usd or 0.0
                p_cost = loaded.paired_eval.pro.cost_usd or 0.0
                total_spent_usd += (f_cost + p_cost)

    def check_budget_or_raise():
        if total_spent_usd + MAX_ESTIMATED_CALL_COST > budget_limit_usd:
            raise PilotBudgetExceededError(
                f"Pilot execution halted by safety guard: Current spend ${total_spent_usd:.4f} + "
                f"estimated next call exceeds approved budget ceiling of ${budget_limit_usd:.2f}."
            )

    paired_results: list[PairedScenario] = []

    # 2. Main 30-scenario paired execution
    for scenario in scenarios:
        tid = scenario.task_id

        # Skip if already completed from previous run
        if tid in completed_scenarios:
            paired_results.append(completed_scenarios[tid])
            continue

        eval_task = scenario.to_eval_task()

        # A. Execute Flash Trial
        check_budget_or_raise()
        flash_record, flash_traj = execute_model_trial(eval_task, trial_idx=1, model=FLASH_MODEL)
        total_spent_usd += (flash_record.cost_usd or 0.0)

        # B. Execute Pro Trial
        check_budget_or_raise()
        pro_record, pro_traj = execute_model_trial(eval_task, trial_idx=1, model=PRO_MODEL)
        total_spent_usd += (pro_record.cost_usd or 0.0)

        # C. Compute paired outcome category
        flash_status = "provider_error" if "provider_error" in flash_record.tier_failures else "completed"
        pro_status = "provider_error" if "provider_error" in pro_record.tier_failures else "completed"

        if flash_status == "provider_error" or pro_status == "provider_error":
            paired_status = "provider_error"
            outcome_cat = "UNDETERMINED"
            escalation = False
        else:
            paired_status = "completed"
            f_pass = bool(flash_record.passed)
            p_pass = bool(pro_record.passed)
            if f_pass and p_pass:
                outcome_cat = "PASS_PASS"
                escalation = False
            elif not f_pass and p_pass:
                outcome_cat = "FAIL_PASS"
                escalation = True
            elif f_pass and not p_pass:
                outcome_cat = "PASS_FAIL"
                escalation = False
            else:
                outcome_cat = "FAIL_FAIL"
                escalation = False

        scenario.paired_eval = PairedEvaluationOutcome(
            status=paired_status,
            flash=flash_record,
            pro=pro_record,
            outcome_category=outcome_cat,
            escalation_benefit=escalation,
            eval_valid=(paired_status == "completed"),
        )

        paired_results.append(scenario)

        # Incremental save to disk
        with results_file.open("a", encoding="utf-8") as f:
            f.write(scenario.model_dump_json() + "\n")

        with trajectories_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"task_id": tid, "model": FLASH_MODEL, "trajectory": flash_traj.model_dump()}) + "\n")
            f.write(json.dumps({"task_id": tid, "model": PRO_MODEL, "trajectory": pro_traj.model_dump()}) + "\n")

        print(
            f"[{len(paired_results)}/{len(scenarios)}] {tid} ({scenario.category}) -> "
            f"Flash: {'PASS' if flash_record.passed else 'FAIL'} | "
            f"Pro: {'PASS' if pro_record.passed else 'FAIL'} | "
            f"Total Spent: ${total_spent_usd:.4f}",
            flush=True,
        )

    # 3. Stochastic Repeat Verification on 5 Representative Scenarios
    stochastic_records: list[dict[str, Any]] = []
    for scenario in paired_results:
        if scenario.task_id not in target_repeats:
            continue

        eval_task = scenario.to_eval_task()
        flash_passes = 1 if scenario.paired_eval.flash.passed else 0
        pro_passes = 1 if scenario.paired_eval.pro.passed else 0
        flash_latencies = [scenario.paired_eval.flash.latency_ms or 0.0]
        pro_latencies = [scenario.paired_eval.pro.latency_ms or 0.0]

        for r_idx in range(2, 2 + repeat_trials):
            # Flash repeat
            check_budget_or_raise()
            f_rec, f_tr = execute_model_trial(eval_task, trial_idx=r_idx, model=FLASH_MODEL)
            total_spent_usd += (f_rec.cost_usd or 0.0)
            if f_rec.passed:
                flash_passes += 1
            flash_latencies.append(f_rec.latency_ms or 0.0)

            # Pro repeat
            check_budget_or_raise()
            p_rec, p_tr = execute_model_trial(eval_task, trial_idx=r_idx, model=PRO_MODEL)
            total_spent_usd += (p_rec.cost_usd or 0.0)
            if p_rec.passed:
                pro_passes += 1
            pro_latencies.append(p_rec.latency_ms or 0.0)

            with trajectories_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"task_id": scenario.task_id, "trial": r_idx, "model": FLASH_MODEL, "trajectory": f_tr.model_dump()}) + "\n")
                f.write(json.dumps({"task_id": scenario.task_id, "trial": r_idx, "model": PRO_MODEL, "trajectory": p_tr.model_dump()}) + "\n")

            print(
                f"[Repeat {r_idx-1}/{repeat_trials}] {scenario.task_id} -> "
                f"Flash: {'PASS' if f_rec.passed else 'FAIL'} | "
                f"Pro: {'PASS' if p_rec.passed else 'FAIL'} | "
                f"Total Spent: ${total_spent_usd:.4f}",
                flush=True,
            )

        total_trials_per_model = 1 + repeat_trials
        stoch_summary = {
            "task_id": scenario.task_id,
            "category": scenario.category,
            "difficulty": scenario.difficulty,
            "total_trials": total_trials_per_model,
            "flash_passes": flash_passes,
            "flash_pass_rate": round(flash_passes / total_trials_per_model, 3),
            "pro_passes": pro_passes,
            "pro_pass_rate": round(pro_passes / total_trials_per_model, 3),
            "flash_mean_latency_ms": round(sum(flash_latencies) / len(flash_latencies), 1),
            "pro_mean_latency_ms": round(sum(pro_latencies) / len(pro_latencies), 1),
        }
        stochastic_records.append(stoch_summary)

        with stochastic_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(stoch_summary) + "\n")

    # 4. Compute Final Aggregate Summary Metrics
    total_scenarios = len(paired_results)
    valid_scenarios = [s for s in paired_results if s.paired_eval.eval_valid]
    v_count = len(valid_scenarios)

    pass_pass = sum(1 for s in valid_scenarios if s.paired_eval.outcome_category == "PASS_PASS")
    fail_pass = sum(1 for s in valid_scenarios if s.paired_eval.outcome_category == "FAIL_PASS")
    pass_fail = sum(1 for s in valid_scenarios if s.paired_eval.outcome_category == "PASS_FAIL")
    fail_fail = sum(1 for s in valid_scenarios if s.paired_eval.outcome_category == "FAIL_FAIL")
    provider_errors = total_scenarios - v_count

    flash_passes = sum(1 for s in valid_scenarios if s.paired_eval.flash.passed)
    pro_passes = sum(1 for s in valid_scenarios if s.paired_eval.pro.passed)

    flash_pass_rate = round(flash_passes / v_count, 4) if v_count else 0.0
    pro_pass_rate = round(pro_passes / v_count, 4) if v_count else 0.0
    disagreement_rate = round((fail_pass + pass_fail) / v_count, 4) if v_count else 0.0

    # Failure category breakdown
    failure_breakdown: dict[str, dict[str, int]] = {}
    for s in valid_scenarios:
        cat = s.category
        failure_breakdown.setdefault(cat, {"flash_fail": 0, "pro_fail": 0, "total": 0})
        failure_breakdown[cat]["total"] += 1
        if not s.paired_eval.flash.passed:
            failure_breakdown[cat]["flash_fail"] += 1
        if not s.paired_eval.pro.passed:
            failure_breakdown[cat]["pro_fail"] += 1

    # Token and latency aggregates
    total_flash_p_tokens = sum(s.paired_eval.flash.prompt_tokens or 0 for s in paired_results)
    total_flash_c_tokens = sum(s.paired_eval.flash.completion_tokens or 0 for s in paired_results)
    total_pro_p_tokens = sum(s.paired_eval.pro.prompt_tokens or 0 for s in paired_results)
    total_pro_c_tokens = sum(s.paired_eval.pro.completion_tokens or 0 for s in paired_results)

    mean_flash_latency = (
        round(sum(s.paired_eval.flash.latency_ms or 0.0 for s in paired_results) / total_scenarios, 1)
        if total_scenarios else 0.0
    )
    mean_pro_latency = (
        round(sum(s.paired_eval.pro.latency_ms or 0.0 for s in paired_results) / total_scenarios, 1)
        if total_scenarios else 0.0
    )

    summary_report = {
        "total_scenarios_evaluated": total_scenarios,
        "valid_evaluations": v_count,
        "provider_errors": provider_errors,
        "flash_pass_rate": flash_pass_rate,
        "pro_pass_rate": pro_pass_rate,
        "disagreement_rate": disagreement_rate,
        "outcome_counts": {
            "PASS_PASS": pass_pass,
            "FAIL_PASS": fail_pass,
            "PASS_FAIL": pass_fail,
            "FAIL_FAIL": fail_fail,
        },
        "failure_categories": failure_breakdown,
        "stochastic_repeats": stochastic_records,
        "measured_usage": {
            "flash_total_prompt_tokens": total_flash_p_tokens,
            "flash_total_completion_tokens": total_flash_c_tokens,
            "pro_total_prompt_tokens": total_pro_p_tokens,
            "pro_total_completion_tokens": total_pro_c_tokens,
            "flash_mean_latency_ms": mean_flash_latency,
            "pro_mean_latency_ms": mean_pro_latency,
            "total_pilot_cost_usd": round(total_spent_usd, 4),
        },
        "artifacts": {
            "results_file": str(results_file),
            "trajectories_file": str(trajectories_file),
            "stochastic_file": str(stochastic_file),
        },
    }

    summary_file = out_dir / "pilot_summary.json"
    summary_file.write_text(json.dumps(summary_report, indent=2), encoding="utf-8")

    return summary_report
