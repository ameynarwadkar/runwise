"""
Stage 4 Targeted Diagnostic Re-run:
1. rw_hard_002 on Gemini 2.5 Flash (with secured list_orders)
2. rw_hard_002 on Gemini 2.5 Pro (with secured list_orders)
3. rw_hard_007 on Gemini 2.5 Pro (resolving 429 quota exhaustion)

Strict budget ceiling: $0.05 USD.
Preserves historical benchmarks and writes output to results/routing/hard_reasoning_final/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runwise.config import get_provider_config
from runwise.evals.hard_reasoning_generator import generate_8_hard_reasoning_scenarios
from runwise.evals.models import Task, TrialOutcome
from runwise.evals.pilot_runner import (
    FLASH_MODEL,
    MAX_ESTIMATED_CALL_COST,
    PRO_MODEL,
    execute_model_trial,
)
from runwise.evals.routing_schema import PairedEvaluationOutcome, PairedScenario, TrialOutcomeRecord

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FINAL_DIR = PROJECT_ROOT / "results" / "routing" / "hard_reasoning_final"
CORRECTED_DIR = PROJECT_ROOT / "results" / "routing" / "hard_reasoning_corrected"
BUDGET_CEILING_USD = 0.05


def main() -> None:
    print("=" * 70)
    print("STAGE 4 TARGETED DIAGNOSTIC RERUN")
    print(f"Target Directory: {FINAL_DIR}")
    print(f"Budget Limit: ${BUDGET_CEILING_USD:.2f} USD")
    print("=" * 70)

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    scenarios_list = generate_8_hard_reasoning_scenarios()
    scenarios_by_id = {s.task_id: s for s in scenarios_list}

    # Initialize LiteLLM credentials for Vertex AI
    get_provider_config(override_model=FLASH_MODEL)

    total_spent_usd = 0.0

    # Load baseline validated paired scenarios from corrected report
    corrected_results_file = CORRECTED_DIR / "pilot_paired_results.jsonl"
    baseline_records: dict[str, dict[str, Any]] = {}
    if corrected_results_file.exists():
        for line in corrected_results_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                baseline_records[rec["task_id"]] = rec

    # Load baseline trajectories
    corrected_traj_file = CORRECTED_DIR / "trajectories.jsonl"
    baseline_trajs: list[dict[str, Any]] = []
    if corrected_traj_file.exists():
        for line in corrected_traj_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                baseline_trajs.append(json.loads(line))

    # Define the 3 targeted calls
    planned_calls = [
        {"task_id": "rw_hard_002", "model": FLASH_MODEL, "label": "Flash on rw_hard_002 (with list_orders)"},
        {"task_id": "rw_hard_002", "model": PRO_MODEL, "label": "Pro on rw_hard_002 (with list_orders)"},
        {"task_id": "rw_hard_007", "model": PRO_MODEL, "label": "Pro on rw_hard_007 (resolving 429)"},
    ]

    new_trajectories: list[dict[str, Any]] = []
    new_outcomes: dict[str, dict[str, Any]] = {}

    for call in planned_calls:
        tid = call["task_id"]
        model = call["model"]
        label = call["label"]
        scenario = scenarios_by_id[tid]
        eval_task = scenario.to_eval_task()

        # Pre-flight budget guard
        if total_spent_usd + MAX_ESTIMATED_CALL_COST > BUDGET_CEILING_USD:
            raise RuntimeError(
                f"Budget check failed: spent ${total_spent_usd:.4f} + est ${MAX_ESTIMATED_CALL_COST:.4f} > limit ${BUDGET_CEILING_USD:.2f}"
            )

        print(f"\n>> Executing: {label} [{model}]")
        outcome_rec, traj = execute_model_trial(eval_task, trial_idx=1, model=model)
        call_cost = outcome_rec.cost_usd or 0.0
        total_spent_usd += call_cost

        print(f"  Result: passed={outcome_rec.passed} | tier_failures={outcome_rec.tier_failures}")
        print(f"  Cost: ${call_cost:.6f} | Latency: {outcome_rec.latency_ms} ms | Tokens: p={outcome_rec.prompt_tokens}, c={outcome_rec.completion_tokens}")
        print(f"  Cumulative Spent: ${total_spent_usd:.4f} USD")
        print(f"  Response: {traj.final_response[:200]}...")

        # Store trajectory
        new_trajectories.append({
            "task_id": tid,
            "model": model,
            "trajectory": traj.model_dump(),
        })

        if tid not in new_outcomes:
            new_outcomes[tid] = {}
        model_key = "flash" if "flash" in model.lower() else "pro"
        new_outcomes[tid][model_key] = {
            "record": outcome_rec,
            "trajectory": traj,
        }

    # Now assemble the final comprehensive 8-scenario results
    final_paired_results: list[dict[str, Any]] = []
    final_trajectories: list[dict[str, Any]] = []

    # Copy untouched baseline trajectories for tasks 1, 3, 4, 5, 6, 8, and Flash on 7
    for t_entry in baseline_trajs:
        tid = t_entry["task_id"]
        model = t_entry["model"]
        if tid == "rw_hard_002":
            continue  # Replaced by fresh run
        if tid == "rw_hard_007" and "pro" in model.lower():
            continue  # Replaced by fresh run
        final_trajectories.append(t_entry)

    # Append new trajectories
    final_trajectories.extend(new_trajectories)

    # Write combined trajectories.jsonl
    traj_out_file = FINAL_DIR / "trajectories.jsonl"
    with traj_out_file.open("w", encoding="utf-8") as f:
        for t in final_trajectories:
            f.write(json.dumps(t) + "\n")

    # Re-evaluate all 8 tasks via replay on sandboxes
    from runwise.evals.replay_corrected_benchmark import replay_trajectory_on_sandbox
    from runwise.agent.trajectory import Trajectory

    trajectories_by_task: dict[str, dict[str, Any]] = {}
    for t in final_trajectories:
        tid = t["task_id"]
        model = t["model"]
        model_key = "flash" if "flash" in model.lower() else "pro"
        if tid not in trajectories_by_task:
            trajectories_by_task[tid] = {}
        trajectories_by_task[tid][model_key] = t

    flash_passes = 0
    pro_passes = 0
    flash_attempts = 0
    pro_attempts = 0
    valid_pairs = 0
    provider_errors_count = 0

    outcome_counts = {
        "PASS_PASS": 0,
        "FAIL_PASS": 0,
        "PASS_FAIL": 0,
        "FAIL_FAIL": 0,
    }

    dimension_metrics = {
        "flash": {"task_completion": 0, "policy_compliance": 0, "factual_correctness": 0, "explanation_quality": 0, "total": 0},
        "pro": {"task_completion": 0, "policy_compliance": 0, "factual_correctness": 0, "explanation_quality": 0, "total": 0},
    }

    usage_metrics = {
        "flash_total_prompt_tokens": 0,
        "flash_total_completion_tokens": 0,
        "pro_total_prompt_tokens": 0,
        "pro_total_completion_tokens": 0,
        "flash_latencies": [],
        "pro_latencies": [],
        "total_cost_usd": 0.0,
    }

    audit_lines: list[str] = []

    for scenario in scenarios_list:
        tid = scenario.task_id
        eval_task = scenario.to_eval_task()
        task_trajs = trajectories_by_task.get(tid, {})

        audit_lines.append("=" * 80)
        audit_lines.append(f"TASK ID: {tid} ({scenario.category})")
        audit_lines.append(f"PROMPT: {eval_task.user_prompt}")

        # Flash eval
        f_entry = task_trajs.get("flash")
        f_rec: TrialOutcomeRecord | None = None
        f_verdict = None
        if f_entry:
            t_obj = Trajectory.model_validate(f_entry["trajectory"])
            u = t_obj.usage
            usage_metrics["flash_total_prompt_tokens"] += (u.prompt_tokens or 0)
            usage_metrics["flash_total_completion_tokens"] += (u.completion_tokens or 0)
            if u.latency_ms:
                usage_metrics["flash_latencies"].append(u.latency_ms)

            from runwise.evals.pilot_runner import compute_trial_cost
            c = compute_trial_cost("flash", u.prompt_tokens or 0, u.completion_tokens or 0)
            usage_metrics["total_cost_usd"] += c

            if t_obj.exit_reason == "PROVIDER_ERROR":
                f_rec = TrialOutcomeRecord(trials_attempted=1, trials_passed=0, passed=None, tier_failures=["provider_error"], cost_usd=round(c, 6))
            else:
                flash_attempts += 1
                session, f_verdict, f_outcome, f_graders = replay_trajectory_on_sandbox(t_obj, eval_task)
                f_passed = f_verdict.overall_pass
                if f_passed:
                    flash_passes += 1
                dimension_metrics["flash"]["total"] += 1
                if f_verdict.task_completion:
                    dimension_metrics["flash"]["task_completion"] += 1
                if f_verdict.policy_compliance:
                    dimension_metrics["flash"]["policy_compliance"] += 1
                if f_verdict.factual_correctness:
                    dimension_metrics["flash"]["factual_correctness"] += 1
                if f_verdict.explanation_quality:
                    dimension_metrics["flash"]["explanation_quality"] += 1

                f_tier_failures = [r.grader_name for r in f_graders if r.status.value == "FAIL"]
                if not f_passed and "policy_critical" not in f_tier_failures:
                    f_tier_failures.append("policy_critical")

                f_rec = TrialOutcomeRecord(
                    trials_attempted=1,
                    trials_passed=1 if f_passed else 0,
                    passed=f_passed,
                    tier_failures=f_tier_failures,
                    latency_ms=round(u.latency_ms or 0.0, 2),
                    prompt_tokens=u.prompt_tokens or 0,
                    completion_tokens=u.completion_tokens or 0,
                    cost_usd=round(c, 6),
                )
                session.conn.close()

        # Pro eval
        p_entry = task_trajs.get("pro")
        p_rec: TrialOutcomeRecord | None = None
        p_verdict = None
        if p_entry:
            t_obj = Trajectory.model_validate(p_entry["trajectory"])
            u = t_obj.usage
            usage_metrics["pro_total_prompt_tokens"] += (u.prompt_tokens or 0)
            usage_metrics["pro_total_completion_tokens"] += (u.completion_tokens or 0)
            if u.latency_ms:
                usage_metrics["pro_latencies"].append(u.latency_ms)

            from runwise.evals.pilot_runner import compute_trial_cost
            c = compute_trial_cost("pro", u.prompt_tokens or 0, u.completion_tokens or 0)
            usage_metrics["total_cost_usd"] += c

            if t_obj.exit_reason == "PROVIDER_ERROR":
                p_rec = TrialOutcomeRecord(trials_attempted=1, trials_passed=0, passed=None, tier_failures=["provider_error"], cost_usd=round(c, 6))
            else:
                pro_attempts += 1
                session, p_verdict, p_outcome, p_graders = replay_trajectory_on_sandbox(t_obj, eval_task)
                p_passed = p_verdict.overall_pass
                if p_passed:
                    pro_passes += 1
                dimension_metrics["pro"]["total"] += 1
                if p_verdict.task_completion:
                    dimension_metrics["pro"]["task_completion"] += 1
                if p_verdict.policy_compliance:
                    dimension_metrics["pro"]["policy_compliance"] += 1
                if p_verdict.factual_correctness:
                    dimension_metrics["pro"]["factual_correctness"] += 1
                if p_verdict.explanation_quality:
                    dimension_metrics["pro"]["explanation_quality"] += 1

                p_tier_failures = [r.grader_name for r in p_graders if r.status.value == "FAIL"]
                if not p_passed and "policy_critical" not in p_tier_failures:
                    p_tier_failures.append("policy_critical")

                p_rec = TrialOutcomeRecord(
                    trials_attempted=1,
                    trials_passed=1 if p_passed else 0,
                    passed=p_passed,
                    tier_failures=p_tier_failures,
                    latency_ms=round(u.latency_ms or 0.0, 2),
                    prompt_tokens=u.prompt_tokens or 0,
                    completion_tokens=u.completion_tokens or 0,
                    cost_usd=round(c, 6),
                )
                session.conn.close()

        # Pair outcome category
        eval_valid = True
        if f_rec is None or p_rec is None or f_rec.passed is None or p_rec.passed is None:
            eval_valid = False
            outcome_category = "UNDETERMINED"
            provider_errors_count += 1
            status_str = "provider_error"
        else:
            valid_pairs += 1
            status_str = "completed"
            if f_rec.passed and p_rec.passed:
                outcome_category = "PASS_PASS"
                outcome_counts["PASS_PASS"] += 1
            elif not f_rec.passed and p_rec.passed:
                outcome_category = "FAIL_PASS"
                outcome_counts["FAIL_PASS"] += 1
            elif f_rec.passed and not p_rec.passed:
                outcome_category = "PASS_FAIL"
                outcome_counts["PASS_FAIL"] += 1
            else:
                outcome_category = "FAIL_FAIL"
                outcome_counts["FAIL_FAIL"] += 1

        escalation_benefit = (outcome_category == "FAIL_PASS")

        paired_eval_dict = {
            "status": status_str,
            "flash": f_rec.model_dump() if f_rec else None,
            "pro": p_rec.model_dump() if p_rec else None,
            "outcome_category": outcome_category,
            "escalation_benefit": escalation_benefit,
            "eval_valid": eval_valid,
            "multi_dimensional": {
                "flash": f_verdict.model_dump() if f_verdict else None,
                "pro": p_verdict.model_dump() if p_verdict else None,
            },
        }

        scenario_dict = scenario.model_dump()
        scenario_dict["paired_eval"] = paired_eval_dict
        final_paired_results.append(scenario_dict)

        audit_lines.append(f"OUTCOME: {outcome_category} (valid: {eval_valid})")
        audit_lines.append(f"  Flash Passed: {f_rec.passed if f_rec else None} | Verdict: {f_verdict.model_dump() if f_verdict else None}")
        audit_lines.append(f"  Pro Passed:   {p_rec.passed if p_rec else None} | Verdict: {p_verdict.model_dump() if p_verdict else None}")
        audit_lines.append("")

    # Save final pilot_paired_results.jsonl
    results_file = FINAL_DIR / "pilot_paired_results.jsonl"
    with results_file.open("w", encoding="utf-8") as f:
        for r in final_paired_results:
            f.write(json.dumps(r) + "\n")

    # Save final detailed_audit.txt
    audit_file = FINAL_DIR / "detailed_audit.txt"
    audit_file.write_text("\n".join(audit_lines), encoding="utf-8")

    flash_pass_rate = round(flash_passes / flash_attempts, 4) if flash_attempts else 0.0
    pro_pass_rate = round(pro_passes / pro_attempts, 4) if pro_attempts else 0.0
    disagreement_rate = round(
        (outcome_counts["FAIL_PASS"] + outcome_counts["PASS_FAIL"]) / valid_pairs, 4
    ) if valid_pairs else 0.0

    f_lat_mean = round(sum(usage_metrics["flash_latencies"]) / len(usage_metrics["flash_latencies"]), 1) if usage_metrics["flash_latencies"] else 0.0
    p_lat_mean = round(sum(usage_metrics["pro_latencies"]) / len(usage_metrics["pro_latencies"]), 1) if usage_metrics["pro_latencies"] else 0.0

    summary = {
        "evaluation_mode": "stage4_final_paired_benchmark",
        "total_scenarios_evaluated": len(scenarios_list),
        "valid_evaluations": valid_pairs,
        "provider_errors": provider_errors_count,
        "flash_pass_rate": flash_pass_rate,
        "pro_pass_rate": pro_pass_rate,
        "disagreement_rate": disagreement_rate,
        "outcome_counts": outcome_counts,
        "multi_dimensional_metrics": {
            "flash": {
                "task_completion_rate": round(dimension_metrics["flash"]["task_completion"] / dimension_metrics["flash"]["total"], 4) if dimension_metrics["flash"]["total"] else 0.0,
                "policy_compliance_rate": round(dimension_metrics["flash"]["policy_compliance"] / dimension_metrics["flash"]["total"], 4) if dimension_metrics["flash"]["total"] else 0.0,
                "factual_correctness_rate": round(dimension_metrics["flash"]["factual_correctness"] / dimension_metrics["flash"]["total"], 4) if dimension_metrics["flash"]["total"] else 0.0,
                "explanation_quality_rate": round(dimension_metrics["flash"]["explanation_quality"] / dimension_metrics["flash"]["total"], 4) if dimension_metrics["flash"]["total"] else 0.0,
                "total_valid_trials": dimension_metrics["flash"]["total"],
            },
            "pro": {
                "task_completion_rate": round(dimension_metrics["pro"]["task_completion"] / dimension_metrics["pro"]["total"], 4) if dimension_metrics["pro"]["total"] else 0.0,
                "policy_compliance_rate": round(dimension_metrics["pro"]["policy_compliance"] / dimension_metrics["pro"]["total"], 4) if dimension_metrics["pro"]["total"] else 0.0,
                "factual_correctness_rate": round(dimension_metrics["pro"]["factual_correctness"] / dimension_metrics["pro"]["total"], 4) if dimension_metrics["pro"]["total"] else 0.0,
                "explanation_quality_rate": round(dimension_metrics["pro"]["explanation_quality"] / dimension_metrics["pro"]["total"], 4) if dimension_metrics["pro"]["total"] else 0.0,
                "total_valid_trials": dimension_metrics["pro"]["total"],
            },
        },
        "measured_usage": {
            "flash_total_prompt_tokens": usage_metrics["flash_total_prompt_tokens"],
            "flash_total_completion_tokens": usage_metrics["flash_total_completion_tokens"],
            "pro_total_prompt_tokens": usage_metrics["pro_total_prompt_tokens"],
            "pro_total_completion_tokens": usage_metrics["pro_total_completion_tokens"],
            "flash_mean_latency_ms": f_lat_mean,
            "pro_mean_latency_ms": p_lat_mean,
            "total_benchmark_cost_usd": round(usage_metrics["total_cost_usd"], 4),
            "rerun_cost_usd": round(total_spent_usd, 4),
        },
        "artifacts": {
            "results_file": str(results_file),
            "summary_file": str(FINAL_DIR / "summary.json"),
            "detailed_audit": str(audit_file),
            "trajectories_file": str(traj_out_file),
        },
    }

    summary_file = FINAL_DIR / "summary.json"
    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print("STAGE 4 FINAL RE-RUN & SYNTHESIS COMPLETED")
    print(f"Rerun Spent: ${total_spent_usd:.4f} USD (budget ceiling: ${BUDGET_CEILING_USD:.2f})")
    print(f"Total Valid Evaluations: {summary['valid_evaluations']} / 8")
    print(f"Provider Errors: {summary['provider_errors']}")
    print(f"Flash Pass Rate: {summary['flash_pass_rate']:.1%}")
    print(f"Pro Pass Rate: {summary['pro_pass_rate']:.1%}")
    print(f"Outcome Distribution: {summary['outcome_counts']}")
    print("Multi-Dimensional Metrics:")
    print("  Flash:", summary["multi_dimensional_metrics"]["flash"])
    print("  Pro:  ", summary["multi_dimensional_metrics"]["pro"])
    print("=" * 70)


if __name__ == "__main__":
    main()
