import { EvaluationSummary, GraderDetail } from "@/lib/types";
import { CheckCircle2, XCircle, AlertCircle, ShieldCheck } from "lucide-react";

interface EvaluationMatrixProps {
  evaluation?: EvaluationSummary | null;
}

export function EvaluationMatrix({ evaluation }: EvaluationMatrixProps) {
  if (!evaluation) {
    return (
      <div className="p-6 text-center text-xs text-slate-400 font-mono">
        <ShieldCheck className="h-8 w-8 text-slate-600 mx-auto mb-2" />
        <p className="text-slate-300 font-semibold">Evaluation Pending</p>
        <p className="mt-1 text-slate-400">
          Run a scenario to trigger deterministic Tiers 1–3 evaluators.
        </p>
      </div>
    );
  }

  const renderBadge = (status: string) => {
    switch (status) {
      case "PASS":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>PASS</span>
          </span>
        );
      case "FAIL":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-bold bg-red-500/15 text-red-400 border border-red-500/30">
            <XCircle className="h-3.5 w-3.5" />
            <span>FAIL</span>
          </span>
        );
      case "NOT_APPLICABLE":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono text-slate-400 bg-slate-800 border border-slate-700">
            <span>N/A</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono text-slate-400 bg-slate-800 border border-slate-700">
            <span>NOT EVALUATED</span>
          </span>
        );
    }
  };

  const isNotEvaluated = evaluation.overall_status === "NOT_EVALUATED";

  return (
    <div className="p-4 space-y-4">
      {/* Overall Verdict Banner */}
      <div
        className={`rounded-xl border p-4 flex items-center justify-between ${
          evaluation.overall_status === "PASS"
            ? "bg-emerald-950/20 border-emerald-500/40"
            : evaluation.overall_status === "FAIL"
            ? "bg-red-950/20 border-red-500/40"
            : "bg-surface border-surface-border"
        }`}
      >
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
            Overall Deterministic Verdict
          </span>
          <div className="text-base font-bold text-white mt-0.5">
            {evaluation.overall_status === "PASS"
              ? "All Policy & State Gates Passed"
              : evaluation.overall_status === "FAIL"
              ? "Invariant Breach Detected"
              : "Ad-hoc Multi-Turn Turn"}
          </div>
        </div>
        <div>{renderBadge(evaluation.overall_status)}</div>
      </div>

      {/* Explanatory Message */}
      <div className="p-3.5 rounded-lg bg-charcoal border border-surface-border text-xs text-slate-300 leading-relaxed font-sans">
        <strong className="text-slate-100 font-mono">Grader Evidence: </strong>
        {evaluation.explanation}
      </div>

      {/* 3-Tier Matrix */}
      <div className="space-y-2.5 font-mono text-xs">
        {/* Tier 1 */}
        <div className="p-3 rounded-lg bg-charcoal border border-surface-border flex items-start justify-between gap-3">
          <div>
            <div className="text-slate-200 font-semibold">Tier 1: Task Completion (DB State)</div>
            <p className="text-[11px] text-slate-400 mt-0.5 font-sans">
              {evaluation.task_completion?.message || "SQL mutation & audit log assertions."}
            </p>
          </div>
          <div>{renderBadge(evaluation.task_completion?.status || "NOT_EVALUATED")}</div>
        </div>

        {/* Tier 2 */}
        <div className="p-3 rounded-lg bg-charcoal border border-surface-border flex items-start justify-between gap-3">
          <div>
            <div className="text-slate-200 font-semibold">Tier 2: Policy Compliance</div>
            <p className="text-[11px] text-slate-400 mt-0.5 font-sans">
              {evaluation.policy_compliance?.message || "Auth-before-action ordering and tool boundaries."}
            </p>
          </div>
          <div>{renderBadge(evaluation.policy_compliance?.status || "NOT_EVALUATED")}</div>
        </div>

        {/* Tier 3 */}
        <div className="p-3 rounded-lg bg-charcoal border border-surface-border flex items-start justify-between gap-3">
          <div>
            <div className="text-slate-200 font-semibold">Tier 3: Groundedness &amp; Truth</div>
            <p className="text-[11px] text-slate-400 mt-0.5 font-sans">
              {evaluation.groundedness?.message || "Regex verification against session SQLite snapshot."}
            </p>
          </div>
          <div>{renderBadge(evaluation.groundedness?.status || "NOT_EVALUATED")}</div>
        </div>
      </div>

      {isNotEvaluated && (
        <div className="p-3 rounded bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 leading-relaxed">
          <strong>Note:</strong> Multi-turn or custom conversational queries are marked NOT EVALUATED because ground-truth SQL assertions exist only for registered evaluation tasks.
        </div>
      )}
    </div>
  );
}
