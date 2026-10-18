"use client";

import { useState } from "react";
import { AgentRunResponse } from "@/lib/types";
import { ExecutionTimeline } from "./ExecutionTimeline";
import { ToolCallsView } from "./ToolCallsView";
import { EvaluationMatrix } from "./EvaluationMatrix";
import { RoutingDiagnostics } from "./RoutingDiagnostics";
import { Clock, Cpu, Wrench, ShieldCheck, Zap, DollarSign } from "lucide-react";

interface ExecutionInspectorProps {
  runData: AgentRunResponse | null;
}

export function ExecutionInspector({ runData }: ExecutionInspectorProps) {
  const [activeTab, setActiveTab] = useState<"timeline" | "tools" | "evals" | "routing">("timeline");

  const modelName = runData?.model ? runData.model.replace("vertex_ai/", "") : "gemini-2.5-flash";
  const isPro = modelName.includes("pro");
  const latency = runData?.latency_ms ? (runData.latency_ms / 1000).toFixed(2) : "0.00";
  const totalTokens = runData?.tokens?.total_tokens ?? 0;
  const cost = runData?.cost_usd;

  return (
    <div className="flex flex-col h-[650px] rounded-xl border border-surface-border bg-charcoal overflow-hidden shadow-xl">
      {/* Top Metrics Strip */}
      <div className="bg-surface/90 border-b border-surface-border p-3.5 sm:p-4 grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs">
        {/* Model */}
        <div className="p-2 rounded bg-charcoal border border-surface-border">
          <span className="text-[10px] text-slate-400 block uppercase">Routed Model</span>
          <span className={`font-bold ${isPro ? "text-brand-purple" : "text-emerald-400"}`}>
            {modelName}
          </span>
        </div>

        {/* Complexity */}
        <div className="p-2 rounded bg-charcoal border border-surface-border">
          <span className="text-[10px] text-slate-400 block uppercase">Complexity</span>
          <span className="font-bold text-white">
            {runData?.complexity_score !== undefined && runData.complexity_score !== null
              ? runData.complexity_score.toFixed(2)
              : "0.00"}
          </span>
        </div>

        {/* Latency */}
        <div className="p-2 rounded bg-charcoal border border-surface-border">
          <span className="text-[10px] text-slate-400 block uppercase">Latency</span>
          <span className="font-bold text-slate-200">{latency}s</span>
        </div>

        {/* Tokens & Cost */}
        <div className="p-2 rounded bg-charcoal border border-surface-border">
          <span className="text-[10px] text-slate-400 block uppercase">Tokens / Cost</span>
          <span className="font-bold text-slate-200">
            {totalTokens}t{" "}
            <span className="text-emerald-400 font-normal">
              {cost !== undefined && cost !== null
                ? `($${cost < 0.0001 ? "<0.0001" : cost.toFixed(4)})`
                : "($0.00)"}
            </span>
          </span>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-surface-border bg-charcoal-subtle text-xs font-medium">
        <button
          onClick={() => setActiveTab("timeline")}
          className={`flex-1 py-2.5 px-3 flex items-center justify-center gap-1.5 border-b-2 transition-all ${
            activeTab === "timeline"
              ? "border-brand-orange text-white bg-surface"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <Clock className="h-3.5 w-3.5" />
          <span>Timeline</span>
          {runData?.events && runData.events.length > 0 && (
            <span className="text-[10px] px-1.5 rounded-full bg-slate-800 text-slate-300">
              {runData.events.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("tools")}
          className={`flex-1 py-2.5 px-3 flex items-center justify-center gap-1.5 border-b-2 transition-all ${
            activeTab === "tools"
              ? "border-brand-orange text-white bg-surface"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <Wrench className="h-3.5 w-3.5" />
          <span>Tools</span>
          {runData?.tool_calls && runData.tool_calls.length > 0 && (
            <span className="text-[10px] px-1.5 rounded-full bg-slate-800 text-brand-orange font-bold">
              {runData.tool_calls.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("evals")}
          className={`flex-1 py-2.5 px-3 flex items-center justify-center gap-1.5 border-b-2 transition-all ${
            activeTab === "evals"
              ? "border-brand-orange text-white bg-surface"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          <span>Evals</span>
          {runData?.evaluation && (
            <span
              className={`text-[10px] px-1.5 rounded-full font-bold ${
                runData.evaluation.overall_status === "PASS"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : runData.evaluation.overall_status === "FAIL"
                  ? "bg-red-500/20 text-red-400"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              {runData.evaluation.overall_status}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("routing")}
          className={`flex-1 py-2.5 px-3 flex items-center justify-center gap-1.5 border-b-2 transition-all ${
            activeTab === "routing"
              ? "border-brand-orange text-white bg-surface"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <Zap className="h-3.5 w-3.5" />
          <span>Routing</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="flex-1 overflow-y-auto bg-charcoal">
        {activeTab === "timeline" && <ExecutionTimeline events={runData?.events || []} />}
        {activeTab === "tools" && <ToolCallsView toolCalls={runData?.tool_calls || []} />}
        {activeTab === "evals" && <EvaluationMatrix evaluation={runData?.evaluation} />}
        {activeTab === "routing" && (
          <RoutingDiagnostics
            model={runData?.model}
            complexityScore={runData?.complexity_score}
            routingReason={runData?.routing_reason}
            featuresDetected={runData?.features_detected}
          />
        )}
      </div>
    </div>
  );
}
