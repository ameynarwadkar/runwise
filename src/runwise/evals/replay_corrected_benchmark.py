"""
Offline Replay Engine for Corrected Benchmark Evaluation.

Replays recorded trajectories from results/routing/hard_reasoning/trajectories.jsonl
through the repaired graders and multi-dimensional evaluation criteria without
incurring any paid model calls.

Preserves original benchmark results and produces:
- results/routing/hard_reasoning_corrected/pilot_paired_results.jsonl
- results/routing/hard_reasoning_corrected/summary.json
- results/routing/hard_reasoning_corrected/detailed_audit.txt
- results/routing/hard_reasoning_corrected/trajectories.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runwise.agent.dispatcher import dispatch_tool_call
from runwise.agent.trajectory import ExitReason, Trajectory, TrajectoryEvent
from runwise.domain.authorization import classify_request_intent
from runwise.domain.db import SandboxDB
from runwise.domain.model import SessionContext
from runwise.evals.graders.aggregation import evaluate_trial
from runwise.evals.graders.trajectory import TrajectoryPolicyGrader
from runwise.evals.hard_reasoning_generator import generate_8_hard_reasoning_scenarios
from runwise.evals.models import GraderResult, GraderStatus, MultiDimensionalVerdict, Task, TrialOutcome
from runwise.evals.routing_schema import PairedEvaluationOutcome, PairedScenario, TrialOutcomeRecord

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ORIGINAL_DIR = PROJECT_ROOT / "results" / "routing" / "hard_reasoning"
CORRECTED_DIR = PROJECT_ROOT / "results" / "routing" / "hard_reasoning_corrected"


def replay_trajectory_on_sandbox(
    trajectory: Trajectory,
    task: Task,
) -> tuple[SessionContext, MultiDimensionalVerdict, TrialOutcome, list[GraderResult]]:
    """
    Spawns a fresh SQLite sandbox with task clock, executes the recorded tool calls,
    and runs multi-dimensional and tiered evaluation.
    """
    conn = SandboxDB.create_connection()
    session = SessionContext(
        conn=conn,
        trial_id=trajectory.trial_id,
        current_time_iso=task.injected_clock_iso,
        authenticated_user_id=None,
    )

    # Apply intent authorization
    intent = classify_request_intent(task.user_prompt)
    session.request_intent = intent.intent_type
    for act_type, oid in intent.authorized_actions:
        session.authorize_action(act_type, oid)

    # Replay tool calls from trajectory events
    for event in trajectory.events:
        if event.event_type == "MODEL_RESPONSE" and event.tool_calls:
            for tc in event.tool_calls:
                func = tc.get("function", {}) if isinstance(tc, dict) else getattr(tc, "function", {})
                name = func.get("name", "") if isinstance(func, dict) else getattr(func, "name", "")
                args_raw = func.get("arguments", "{}") if isinstance(func, dict) else getattr(func, "arguments", "{}")
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {}
                else:
                    args = args_raw or {}

                dispatch_tool_call(session, tool_name=name, arguments=args)

    # Evaluate multi-dimensional verdict (with check_db=True since DB was replayed)
    verdict = TrajectoryPolicyGrader.evaluate_dimensions(
        trajectory=trajectory,
        task=task,
        conn=conn,
        check_db=True,
    )

    # Tiered aggregation evaluation
    outcome, grader_results = evaluate_trial(trajectory, task, conn=conn)

    return session, verdict, outcome, grader_results


def run_corrected_replay() -> dict[str, Any]:
    CORRECTED_DIR.mkdir(parents=True, exist_ok=True)
    scenarios_list = generate_8_hard_reasoning_scenarios()
    scenarios_by_id = {s.task_id: s for s in scenarios_list}

    # Load trajectories
    traj_file = ORIGINAL_DIR / "trajectories.jsonl"
    if not traj_file.exists():
        raise FileNotFoundError(f"Trajectories file not found at {traj_file}")

    trajectories_by_task: dict[str, dict[str, Any]] = {}
    with traj_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            tid = entry["task_id"]
            model = entry["model"]
            model_key = "flash" if "flash" in model.lower() else "pro"
            if tid not in trajectories_by_task:
                trajectories_by_task[tid] = {}
            trajectories_by_task[tid][model_key] = entry

    # Copy trajectories.jsonl to corrected dir to preserve full package
    corrected_traj_file = CORRECTED_DIR / "trajectories.jsonl"
    corrected_traj_file.write_text(traj_file.read_text(encoding="utf-8"), encoding="utf-8")

    paired_results: list[dict[str, Any]] = []
    audit_lines: list[str] = []

    # Aggregates
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

    for scenario in scenarios_list:
        tid = scenario.task_id
        eval_task = scenario.to_eval_task()
        task_trajs = trajectories_by_task.get(tid, {})

        audit_lines.append("=" * 80)
        audit_lines.append(f"TASK ID: {tid} ({scenario.category})")
        audit_lines.append(f"PROMPT: {eval_task.user_prompt}")
        audit_lines.append(f"REQUIRED TOOLS: {eval_task.expected.required_tools}")
        audit_lines.append(f"ALLOWED TOOL PATHS: {eval_task.expected.allowed_tool_paths}")
        audit_lines.append(f"FACTUAL PATTERNS: {eval_task.expected.factual_patterns}")
        audit_lines.append(f"EXPLANATION PATTERNS: {eval_task.expected.explanation_patterns}")
        audit_lines.append(f"REFUSAL PATTERNS: {eval_task.expected.refusal_patterns}")

        # Flash Evaluation
        flash_entry = task_trajs.get("flash")
        flash_record: TrialOutcomeRecord | None = None
        flash_verdict: MultiDimensionalVerdict | None = None
        if flash_entry:
            t_dict = flash_entry["trajectory"]
            flash_traj = Trajectory.model_validate(t_dict)
            usage = flash_traj.usage
            usage_metrics["flash_total_prompt_tokens"] += (usage.prompt_tokens or 0)
            usage_metrics["flash_total_completion_tokens"] += (usage.completion_tokens or 0)
            if usage.latency_ms:
                usage_metrics["flash_latencies"].append(usage.latency_ms)

            # Compute cost
            from runwise.evals.pilot_runner import compute_trial_cost
            f_cost = compute_trial_cost("flash", usage.prompt_tokens or 0, usage.completion_tokens or 0)
            usage_metrics["total_cost_usd"] += f_cost

            if flash_traj.exit_reason == ExitReason.PROVIDER_ERROR:
                flash_record = TrialOutcomeRecord(
                    trials_attempted=1,
                    trials_passed=0,
                    passed=None,
                    tier_failures=["provider_error"],
                    latency_ms=round(usage.latency_ms or 0.0, 2),
                    prompt_tokens=usage.prompt_tokens or 0,
                    completion_tokens=usage.completion_tokens or 0,
                    cost_usd=round(f_cost, 6),
                )
            else:
                flash_attempts += 1
                session, flash_verdict, flash_outcome, f_graders = replay_trajectory_on_sandbox(flash_traj, eval_task)
                f_passed = flash_verdict.overall_pass
                if f_passed:
                    flash_passes += 1

                dimension_metrics["flash"]["total"] += 1
                if flash_verdict.task_completion:
                    dimension_metrics["flash"]["task_completion"] += 1
                if flash_verdict.policy_compliance:
                    dimension_metrics["flash"]["policy_compliance"] += 1
                if flash_verdict.factual_correctness:
                    dimension_metrics["flash"]["factual_correctness"] += 1
                if flash_verdict.explanation_quality:
                    dimension_metrics["flash"]["explanation_quality"] += 1

                f_tier_failures = [r.grader_name for r in f_graders if r.status == GraderStatus.FAIL]
                if not f_passed and "policy_critical" not in f_tier_failures:
                    f_tier_failures.append("policy_critical")

                flash_record = TrialOutcomeRecord(
                    trials_attempted=1,
                    trials_passed=1 if f_passed else 0,
                    passed=f_passed,
                    tier_failures=f_tier_failures,
                    latency_ms=round(usage.latency_ms or 0.0, 2),
                    prompt_tokens=usage.prompt_tokens or 0,
                    completion_tokens=usage.completion_tokens or 0,
                    cost_usd=round(f_cost, 6),
                )
                session.conn.close()

        # Pro Evaluation
        pro_entry = task_trajs.get("pro")
        pro_record: TrialOutcomeRecord | None = None
        pro_verdict: MultiDimensionalVerdict | None = None
        if pro_entry:
            t_dict = pro_entry["trajectory"]
            pro_traj = Trajectory.model_validate(t_dict)
            usage = pro_traj.usage
            usage_metrics["pro_total_prompt_tokens"] += (usage.prompt_tokens or 0)
            usage_metrics["pro_total_completion_tokens"] += (usage.completion_tokens or 0)
            if usage.latency_ms:
                usage_metrics["pro_latencies"].append(usage.latency_ms)

            from runwise.evals.pilot_runner import compute_trial_cost
            p_cost = compute_trial_cost("pro", usage.prompt_tokens or 0, usage.completion_tokens or 0)
            usage_metrics["total_cost_usd"] += p_cost

            if pro_traj.exit_reason == ExitReason.PROVIDER_ERROR:
                pro_record = TrialOutcomeRecord(
                    trials_attempted=1,
                    trials_passed=0,
                    passed=None,
                    tier_failures=["provider_error"],
                    latency_ms=round(usage.latency_ms or 0.0, 2),
                    prompt_tokens=usage.prompt_tokens or 0,
                    completion_tokens=usage.completion_tokens or 0,
                    cost_usd=round(p_cost, 6),
                )
            else:
                pro_attempts += 1
                session, pro_verdict, pro_outcome, p_graders = replay_trajectory_on_sandbox(pro_traj, eval_task)
                p_passed = pro_verdict.overall_pass
                if p_passed:
                    pro_passes += 1

                dimension_metrics["pro"]["total"] += 1
                if pro_verdict.task_completion:
                    dimension_metrics["pro"]["task_completion"] += 1
                if pro_verdict.policy_compliance:
                    dimension_metrics["pro"]["policy_compliance"] += 1
                if pro_verdict.factual_correctness:
                    dimension_metrics["pro"]["factual_correctness"] += 1
                if pro_verdict.explanation_quality:
                    dimension_metrics["pro"]["explanation_quality"] += 1

                p_tier_failures = [r.grader_name for r in p_graders if r.status == GraderStatus.FAIL]
                if not p_passed and "policy_critical" not in p_tier_failures:
                    p_tier_failures.append("policy_critical")

                pro_record = TrialOutcomeRecord(
                    trials_attempted=1,
                    trials_passed=1 if p_passed else 0,
                    passed=p_passed,
                    tier_failures=p_tier_failures,
                    latency_ms=round(usage.latency_ms or 0.0, 2),
                    prompt_tokens=usage.prompt_tokens or 0,
                    completion_tokens=usage.completion_tokens or 0,
                    cost_usd=round(p_cost, 6),
                )
                session.conn.close()

        # Pair outcome category
        eval_valid = True
        if flash_record is None or pro_record is None or flash_record.passed is None or pro_record.passed is None:
            eval_valid = False
            outcome_category = "UNDETERMINED"
            provider_errors_count += 1
            status_str = "provider_error"
        else:
            valid_pairs += 1
            status_str = "completed"
            if flash_record.passed and pro_record.passed:
                outcome_category = "PASS_PASS"
                outcome_counts["PASS_PASS"] += 1
            elif not flash_record.passed and pro_record.passed:
                outcome_category = "FAIL_PASS"
                outcome_counts["FAIL_PASS"] += 1
            elif flash_record.passed and not pro_record.passed:
                outcome_category = "PASS_FAIL"
                outcome_counts["PASS_FAIL"] += 1
            else:
                outcome_category = "FAIL_FAIL"
                outcome_counts["FAIL_FAIL"] += 1

        escalation_benefit = (outcome_category == "FAIL_PASS")

        paired_eval_dict = {
            "status": status_str,
            "flash": flash_record.model_dump() if flash_record else None,
            "pro": pro_record.model_dump() if pro_record else None,
            "outcome_category": outcome_category,
            "escalation_benefit": escalation_benefit,
            "eval_valid": eval_valid,
            "multi_dimensional": {
                "flash": flash_verdict.model_dump() if flash_verdict else None,
                "pro": pro_verdict.model_dump() if pro_verdict else None,
            },
        }

        # Build updated PairedScenario record
        scenario_dict = scenario.model_dump()
        scenario_dict["paired_eval"] = paired_eval_dict
        paired_results.append(scenario_dict)

        # Audit lines
        audit_lines.append(f"OUTCOME: {outcome_category} (valid: {eval_valid})")
        audit_lines.append("----------------------------------------")
        audit_lines.append("  --- MODEL: vertex_ai/gemini-2.5-flash ---")
        if flash_record:
            audit_lines.append(f"  Result: passed={flash_record.passed} | tier_failures={flash_record.tier_failures}")
        if flash_verdict:
            audit_lines.append(f"  Multi-Dimensional Verdict: {flash_verdict.model_dump()}")
        audit_lines.append(f"  Response: {task_trajs.get('flash', {}).get('trajectory', {}).get('final_response')}")
        audit_lines.append("")
        audit_lines.append("  --- MODEL: vertex_ai/gemini-2.5-pro ---")
        if pro_record:
            audit_lines.append(f"  Result: passed={pro_record.passed} | tier_failures={pro_record.tier_failures}")
        if pro_verdict:
            audit_lines.append(f"  Multi-Dimensional Verdict: {pro_verdict.model_dump()}")
        audit_lines.append(f"  Response: {task_trajs.get('pro', {}).get('trajectory', {}).get('final_response')}")
        audit_lines.append("")

    # Save pilot_paired_results.jsonl
    results_file = CORRECTED_DIR / "pilot_paired_results.jsonl"
    with results_file.open("w", encoding="utf-8") as f:
        for r in paired_results:
            f.write(json.dumps(r) + "\n")

    # Save detailed_audit.txt
    audit_file = CORRECTED_DIR / "detailed_audit.txt"
    audit_file.write_text("\n".join(audit_lines), encoding="utf-8")

    flash_pass_rate = round(flash_passes / flash_attempts, 4) if flash_attempts else 0.0
    pro_pass_rate = round(pro_passes / pro_attempts, 4) if pro_attempts else 0.0
    disagreement_rate = round(
        (outcome_counts["FAIL_PASS"] + outcome_counts["PASS_FAIL"]) / valid_pairs, 4
    ) if valid_pairs else 0.0

    f_lat_mean = (
        round(sum(usage_metrics["flash_latencies"]) / len(usage_metrics["flash_latencies"]), 1)
        if usage_metrics["flash_latencies"]
        else 0.0
    )
    p_lat_mean = (
        round(sum(usage_metrics["pro_latencies"]) / len(usage_metrics["pro_latencies"]), 1)
        if usage_metrics["pro_latencies"]
        else 0.0
    )

    summary = {
        "evaluation_mode": "corrected_offline_trajectory_replay",
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
            "total_replayed_cost_usd": round(usage_metrics["total_cost_usd"], 4),
        },
        "artifacts": {
            "results_file": str(results_file),
            "summary_file": str(CORRECTED_DIR / "summary.json"),
            "detailed_audit": str(audit_file),
            "trajectories_file": str(corrected_traj_file),
        },
    }

    summary_file = CORRECTED_DIR / "summary.json"
    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    summary = run_corrected_replay()
    print("=" * 70)
    print("CORRECTED BENCHMARK REPLAY COMPLETED")
    print(f"Valid Evaluations: {summary['valid_evaluations']}")
    print(f"Provider Errors: {summary['provider_errors']}")
    print(f"Flash Pass Rate: {summary['flash_pass_rate']:.1%}")
    print(f"Pro Pass Rate: {summary['pro_pass_rate']:.1%}")
    print(f"Disagreement Rate: {summary['disagreement_rate']:.1%}")
    print(f"Outcome Distribution: {summary['outcome_counts']}")
    print("Multi-Dimensional Metrics:")
    print("  Flash:", summary["multi_dimensional_metrics"]["flash"])
    print("  Pro:  ", summary["multi_dimensional_metrics"]["pro"])
    print("=" * 70)
