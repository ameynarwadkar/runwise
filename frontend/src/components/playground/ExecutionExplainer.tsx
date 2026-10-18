"use client";

import { useState } from "react";
import { AgentRunResponse } from "@/lib/types";
import { ExecutionInspector } from "./ExecutionInspector";
import {
  Cpu,
  Wrench,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  Zap,
} from "lucide-react";

interface ExecutionExplainerProps {
  runData?: AgentRunResponse;
}

export function ExecutionExplainer({ runData }: ExecutionExplainerProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [copiedSession, setCopiedSession] = useState(false);

  if (!runData) {
    return (
      <div className="mt-3 p-4 rounded-xl bg-surface border border-surface-border text-xs text-slate-400">
        No execution trace available for this turn.
      </div>
    );
  }

  // 1. Model & Routing Rationale
  const rawModel = runData.model || "gemini-2.5-flash";
  const isPro = rawModel.toLowerCase().includes("pro");
  const modelDisplayName = isPro ? "Gemini 2.5 Pro" : "Gemini 2.5 Flash";

  let routingWhy = "";
  if (runData.routing_reason) {
    routingWhy = runData.routing_reason;
  } else if (runData.complexity_score !== undefined && runData.complexity_score !== null) {
    if (runData.complexity_score < 0.45) {
      routingWhy = `Routine customer inquiry with low liability risk score (${runData.complexity_score.toFixed(2)} < 0.45). Routed to Flash for sub-second response and 57.5% lower cost.`;
    } else {
      routingWhy = `Complex, financial, or adversarial pattern detected (risk score ${runData.complexity_score.toFixed(2)} ≥ 0.45). Routed to Pro for deep multi-step reasoning.`;
    }
  } else {
    routingWhy = isPro
      ? "High-liability reasoning task routed to Gemini Pro."
      : "Standard inquiry routed to Gemini Flash for low-latency execution.";
  }

  // 2. Tools & Accomplishments
  const toolCalls = runData.tool_calls || [];
  const toolSummaries: string[] = [];

  if (toolCalls.length === 0) {
    toolSummaries.push("Direct response generated without requiring database lookups or tool mutations.");
  } else {
    toolCalls.forEach((t) => {
      const toolName = t.tool_name || "tool";
      switch (toolName) {
        case "lookup_order":
          toolSummaries.push(
            `lookup_order: Checked order status, tracking number, and line items in sandboxed database.`
          );
          break;
        case "verify_customer":
          toolSummaries.push(
            `verify_customer: Authenticated customer credentials (${t.arguments?.customer_id || "customer"}) before authorizing mutations.`
          );
          break;
        case "update_shipping_address":
          toolSummaries.push(
            `update_shipping_address: Mutated shipping address in sandboxed SQLite store after verifying authorization.`
          );
          break;
        case "issue_refund":
          toolSummaries.push(
            `issue_refund: Evaluated 30-day post-delivery eligibility and recorded refund against order.`
          );
          break;
        case "cancel_order":
          toolSummaries.push(
            `cancel_order: Verified pending status and updated order record to cancelled in sandboxed database.`
          );
          break;
        default:
          toolSummaries.push(`${toolName}: Executed with status ${t.status}.`);
      }
    });
  }

  // 3. Evaluation Outcome & Assertions
  const evalStatus = runData.evaluation?.overall_status || "NOT_EVALUATED";
  let evalSummary = "";
  if (evalStatus === "PASS") {
    evalSummary =
      "Passed deterministic grading: Database state assertions verified in sandboxed SQLite, auth-before-action policy verified, and response groundedness checks passed.";
  } else if (evalStatus === "FAIL") {
    evalSummary =
      "Evaluation failed: Deterministic assertion detected state discrepancy or policy ordering violation.";
  } else {
    evalSummary =
      "Conversational turn: Not evaluated against pre-registered ground-truth benchmarks.";
  }

  const copySessionId = () => {
    if (runData.session_id) {
      navigator.clipboard.writeText(runData.session_id);
      setCopiedSession(true);
      setTimeout(() => setCopiedSession(false), 2000);
    }
  };

  return (
    <div className="mt-3 rounded-xl border border-surface-border bg-charcoal-subtle p-4 sm:p-5 text-xs text-slate-300">
      <div className="text-xs font-mono font-semibold uppercase tracking-wider text-brand-orange mb-3">
        Execution Breakdown
      </div>

      {/* 3 Human-Readable Steps */}
      <div className="space-y-3.5">
        {/* Step 1: Model Selection */}
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-surface border border-surface-border text-brand-orange">
            <Cpu className="h-3.5 w-3.5" />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-white flex items-center gap-2">
              <span>Model Routing:</span>
              <span className={`font-mono text-[11px] ${isPro ? "text-brand-purple" : "text-emerald-400"}`}>
                {modelDisplayName}
              </span>
            </div>
            <p className="mt-0.5 text-slate-300 leading-relaxed">{routingWhy}</p>
          </div>
        </div>

        {/* Step 2: Tools Used */}
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-surface border border-surface-border text-brand-orange">
            <Wrench className="h-3.5 w-3.5" />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-white">
              Tools Executed ({toolCalls.length}):
            </div>
            <ul className="mt-1 space-y-1 text-slate-300 leading-relaxed list-disc list-inside">
              {toolSummaries.map((summary, idx) => (
                <li key={idx} className="marker:text-brand-orange">
                  {summary}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Step 3: Evaluation Outcome */}
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-surface border border-surface-border text-brand-orange">
            <ShieldCheck className="h-3.5 w-3.5" />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-white flex items-center gap-2">
              <span>Evaluation Outcome:</span>
              <span
                className={`font-mono text-[11px] px-1.5 py-0.5 rounded font-semibold ${
                  evalStatus === "PASS"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : evalStatus === "FAIL"
                    ? "bg-red-500/20 text-red-400"
                    : "bg-slate-800 text-slate-400"
                }`}
              >
                {evalStatus === "PASS" ? "Verified Pass" : evalStatus === "FAIL" ? "Assertion Failure" : "Not Evaluated"}
              </span>
            </div>
            <p className="mt-0.5 text-slate-300 leading-relaxed">{evalSummary}</p>
          </div>
        </div>
      </div>

      {/* Progressive Disclosure: Advanced Technical Details */}
      <div className="mt-4 pt-3.5 border-t border-surface-border/70">
        <button
          onClick={() => setShowAdvanced((prev) => !prev)}
          className="inline-flex items-center gap-1.5 text-xs font-mono font-medium text-slate-400 hover:text-white transition-colors"
        >
          {showAdvanced ? (
            <>
              <ChevronUp className="h-3.5 w-3.5 text-brand-orange" />
              <span>Hide advanced technical details</span>
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5 text-brand-orange" />
              <span>Advanced technical details (timeline, OTel, telemetry, raw tokens)</span>
            </>
          )}
        </button>

        {showAdvanced && (
          <div className="mt-4 space-y-4 animate-in fade-in duration-150">
            {/* Session ID Strip */}
            <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-surface border border-surface-border text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="text-slate-400">Session ID:</span>
                <span className="text-white select-all">{runData.session_id}</span>
              </div>
              <button
                onClick={copySessionId}
                className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white transition-colors px-2 py-0.5 rounded bg-charcoal border border-surface-border"
                title="Copy Session ID"
              >
                {copiedSession ? (
                  <>
                    <Check className="h-3 w-3 text-emerald-400" />
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>

            {/* Token & Pricing Strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
              <div className="p-2 rounded bg-surface border border-surface-border">
                <span className="text-slate-400 block text-[10px]">PROMPT TOKENS</span>
                <span className="font-bold text-white">{runData.tokens?.prompt_tokens ?? 0}</span>
              </div>
              <div className="p-2 rounded bg-surface border border-surface-border">
                <span className="text-slate-400 block text-[10px]">COMPLETION</span>
                <span className="font-bold text-white">{runData.tokens?.completion_tokens ?? 0}</span>
              </div>
              <div className="p-2 rounded bg-surface border border-surface-border">
                <span className="text-slate-400 block text-[10px]">ESTIMATED COST</span>
                <span className="font-bold text-emerald-400">
                  {runData.cost_usd !== undefined && runData.cost_usd !== null
                    ? `$${runData.cost_usd.toFixed(5)}`
                    : "$0.00000"}
                </span>
              </div>
              <div className="p-2 rounded bg-surface border border-surface-border">
                <span className="text-slate-400 block text-[10px]">COMPLEXITY SCORE</span>
                <span className="font-bold text-white">
                  {runData.complexity_score !== undefined && runData.complexity_score !== null
                    ? runData.complexity_score.toFixed(3)
                    : "0.000"}
                </span>
              </div>
            </div>

            {/* Full 4-tab Inspector */}
            <div className="rounded-xl overflow-hidden border border-surface-border shadow-md">
              <ExecutionInspector runData={runData} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
