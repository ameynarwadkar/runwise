"use client";

import { useState } from "react";
import { Cpu, ShieldCheck, Gauge, ArrowRight, CheckCircle2 } from "lucide-react";

export function ArchitectureExplorer() {
  const [activeTab, setActiveTab] = useState<"execution" | "reliability" | "operations">("execution");
  const [executionTier, setExecutionTier] = useState<"flash" | "pro">("flash");

  return (
    <section id="architecture" className="py-16 bg-charcoal border-t border-surface-border">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-10">
          <span className="text-xs font-mono uppercase tracking-widest text-brand-orange font-semibold">
            System Architecture
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mt-1">
            Three Reliability Pillars
          </h2>
          <p className="mt-3 text-base text-slate-300 leading-relaxed">
            Engineered for low-latency routing, deterministic evaluations, and zero-downtime recovery.
          </p>

          {/* 3-View Tab Selector */}
          <div className="mt-7 inline-flex p-1 rounded-xl bg-surface border border-surface-border shadow-sm">
            <button
              onClick={() => setActiveTab("execution")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "execution"
                  ? "bg-brand-orange text-white shadow-sm"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              <Cpu className="h-4 w-4" />
              <span>01 Execution</span>
            </button>
            <button
              onClick={() => setActiveTab("reliability")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "reliability"
                  ? "bg-brand-orange text-white shadow-sm"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              <ShieldCheck className="h-4 w-4" />
              <span>02 Reliability</span>
            </button>
            <button
              onClick={() => setActiveTab("operations")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "operations"
                  ? "bg-brand-orange text-white shadow-sm"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              <Gauge className="h-4 w-4" />
              <span>03 Operations</span>
            </button>
          </div>
        </div>

        {/* Tab 1: Execution */}
        {activeTab === "execution" && (
          <div className="rounded-2xl border border-surface-border bg-surface p-7 sm:p-9 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
              <div>
                <h3 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                  Dynamic Model Tiering
                </h3>
                <p className="text-sm text-slate-300 mt-1">
                  Scores lexical risk in &lt; 0.1ms on CPU, dispatching routine queries to Flash and reserving Pro for complex edge cases.
                </p>
              </div>

              {/* Interactive Router Switcher */}
              <div className="inline-flex p-1 rounded-lg bg-charcoal border border-surface-border text-xs font-mono self-start sm:self-auto">
                <button
                  onClick={() => setExecutionTier("flash")}
                  className={`px-3 py-1.5 rounded transition-all font-semibold ${
                    executionTier === "flash"
                      ? "bg-emerald-500 text-white shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Standard Inquiry (Flash)
                </button>
                <button
                  onClick={() => setExecutionTier("pro")}
                  className={`px-3 py-1.5 rounded transition-all font-semibold ${
                    executionTier === "pro"
                      ? "bg-brand-orange text-white shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Adversarial Query (Pro)
                </button>
              </div>
            </div>

            {/* Clean Flow Diagram */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-center text-center font-mono">
              <div className="rounded-xl bg-charcoal border border-surface-border p-5">
                <span className="text-xs text-slate-400 uppercase">Input</span>
                <div className="text-base font-bold text-white mt-1">User Request</div>
                <span className="text-xs text-slate-400 mt-1 block">Sanitized Prompt</span>
              </div>

              <div className="rounded-xl bg-charcoal border border-brand-orange/40 p-5 shadow-[0_0_15px_rgba(249,115,22,0.1)]">
                <span className="text-xs text-brand-orange uppercase font-semibold">Classifier</span>
                <div className="text-base font-bold text-white mt-1">AutoRouter</div>
                <span className="text-xs text-brand-orange font-mono mt-1 block">
                  {executionTier === "flash" ? "Score: 0.12 (< 0.45)" : "Score: 0.95 (>= 0.45)"}
                </span>
              </div>

              <div
                className={`rounded-xl bg-charcoal p-5 border transition-all ${
                  executionTier === "flash"
                    ? "border-emerald-500 bg-emerald-950/20 shadow-[0_0_15px_rgba(16,185,129,0.15)] ring-1 ring-emerald-500"
                    : "border-brand-orange bg-brand-orange/10 shadow-[0_0_15px_rgba(249,115,22,0.15)] ring-1 ring-brand-orange"
                }`}
              >
                <span className="text-xs uppercase font-semibold text-slate-300">Target Model</span>
                <div className="text-base font-bold text-white mt-1">
                  {executionTier === "flash" ? "Gemini 2.5 Flash" : "Gemini 2.5 Pro"}
                </div>
                <span className="text-xs text-slate-300 mt-1 block">
                  {executionTier === "flash" ? "$0.075 / 1M tokens" : "$1.250 / 1M tokens"}
                </span>
              </div>

              <div className="rounded-xl bg-charcoal border border-surface-border p-5">
                <span className="text-xs text-slate-400 uppercase">Execution</span>
                <div className="text-base font-bold text-white mt-1">SandboxDB</div>
                <span className="text-xs text-emerald-400 mt-1 block">&lt; 2ms SQLite</span>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Reliability */}
        {activeTab === "reliability" && (
          <div className="rounded-2xl border border-surface-border bg-surface p-7 sm:p-9 shadow-xl">
            <div className="mb-8">
              <h3 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                Deterministic 4-Tier Grading
              </h3>
              <p className="text-sm text-slate-300 mt-1">
                Deterministic database state assertions and trajectory policy checks always supersede subjective model outputs.
              </p>
            </div>

            {/* 4 Clean Grader Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-center">
              <div className="rounded-xl bg-charcoal border border-surface-border p-5">
                <span className="text-xs font-mono text-brand-orange font-semibold uppercase">Tier 1</span>
                <div className="text-base font-bold text-white mt-1">State Auditor</div>
                <span className="text-xs text-slate-300 mt-1 block">Exact SQL assertions</span>
              </div>

              <div className="rounded-xl bg-charcoal border border-surface-border p-5">
                <span className="text-xs font-mono text-brand-orange font-semibold uppercase">Tier 2</span>
                <div className="text-base font-bold text-white mt-1">Policy Grader</div>
                <span className="text-xs text-slate-300 mt-1 block">Auth ordering checks</span>
              </div>

              <div className="rounded-xl bg-charcoal border border-surface-border p-5">
                <span className="text-xs font-mono text-brand-orange font-semibold uppercase">Tier 3</span>
                <div className="text-base font-bold text-white mt-1">Groundedness</div>
                <span className="text-xs text-slate-300 mt-1 block">Regex hallucination audit</span>
              </div>

              <div className="rounded-xl bg-charcoal border border-surface-border p-5">
                <span className="text-xs font-mono text-brand-orange font-semibold uppercase">Tier 4</span>
                <div className="text-base font-bold text-white mt-1">CI Regression Gate</div>
                <span className="text-xs text-emerald-400 mt-1 block">Blocks &gt; 2% pass drops</span>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Operations */}
        {activeTab === "operations" && (
          <div className="rounded-2xl border border-surface-border bg-surface p-7 sm:p-9 shadow-xl">
            <div className="mb-8">
              <h3 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                Canary Pinning & Instant Rollback
              </h3>
              <p className="text-sm text-slate-300 mt-1">
                Cryptographically pins sessions to prompt variants, with sub-200ms hot rollback upon latency or error SLO breaches.
              </p>
            </div>

            {/* Clean Pipeline Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-center">
              <div className="rounded-xl bg-charcoal border border-surface-border p-5">
                <span className="text-xs font-mono text-slate-400 uppercase">Routing</span>
                <div className="text-base font-bold text-white mt-1">Session Pinning</div>
                <span className="text-xs text-slate-300 mt-1 block">Sticky hash consistency</span>
              </div>

              <div className="rounded-xl bg-charcoal border border-surface-border p-5">
                <span className="text-xs font-mono text-slate-400 uppercase">Telemetry</span>
                <div className="text-base font-bold text-white mt-1">OTel & Metrics</div>
                <span className="text-xs text-slate-300 mt-1 block">W3C traceparent</span>
              </div>

              <div className="rounded-xl bg-charcoal border border-surface-border p-5">
                <span className="text-xs font-mono text-slate-400 uppercase">Monitoring</span>
                <div className="text-base font-bold text-white mt-1">SLO Alerting</div>
                <span className="text-xs text-slate-300 mt-1 block">p95 &lt; 3,000ms latency</span>
              </div>

              <div className="rounded-xl bg-charcoal border border-emerald-500/40 p-5 shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                <span className="text-xs font-mono text-emerald-400 font-semibold uppercase">Recovery</span>
                <div className="text-base font-bold text-white mt-1">Instant Rollback</div>
                <span className="text-xs text-emerald-400 font-mono mt-1 block">&lt; 200ms zero rebuild</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
