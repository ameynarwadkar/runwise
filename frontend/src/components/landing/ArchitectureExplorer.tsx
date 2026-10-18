"use client";

import { useState } from "react";
import { Cpu, ShieldCheck, Gauge, ArrowRight, Database, Terminal, AlertTriangle, Layers } from "lucide-react";

export function ArchitectureExplorer() {
  const [activeTab, setActiveTab] = useState<"execution" | "reliability" | "operations">("execution");

  return (
    <section id="architecture" className="py-20 bg-charcoal">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <h2 className="text-xs font-mono uppercase tracking-widest text-brand-orange mb-2">
            Engineering Architecture
          </h2>
          <h3 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            Three Integrated Reliability Pillars
          </h3>
          <p className="mt-3 text-base text-slate-400">
            A modular production stack designed for low-latency reasoning, deterministic evaluation, and zero-downtime operational fault tolerance.
          </p>

          {/* 3-View Tab Selector */}
          <div className="mt-8 inline-flex p-1 rounded-xl bg-surface border border-surface-border">
            <button
              onClick={() => setActiveTab("execution")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "execution"
                  ? "bg-brand-orange text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Cpu className="h-4 w-4" />
              <span>01 Execution</span>
            </button>
            <button
              onClick={() => setActiveTab("reliability")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "reliability"
                  ? "bg-brand-orange text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <ShieldCheck className="h-4 w-4" />
              <span>02 Reliability</span>
            </button>
            <button
              onClick={() => setActiveTab("operations")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "operations"
                  ? "bg-brand-orange text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Gauge className="h-4 w-4" />
              <span>03 Operations</span>
            </button>
          </div>
        </div>

        {/* Tab 1: Execution Pipeline */}
        {activeTab === "execution" && (
          <div className="rounded-2xl border border-surface-border bg-surface p-6 sm:p-8 shadow-xl">
            <div className="flex flex-col lg:flex-row gap-8 items-start justify-between">
              <div className="max-w-xl">
                <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-charcoal border border-surface-border text-xs font-mono text-brand-orange mb-3">
                  <span>Proactive Routing</span>
                  <span>•</span>
                  <span>&lt; 0.1ms CPU Overhead</span>
                </div>
                <h4 className="text-2xl font-bold text-white tracking-tight">
                  Cost-Aware Auto-Routing & Sandboxed Execution
                </h4>
                <p className="mt-3 text-slate-300 text-sm leading-relaxed">
                  Rather than wasting 300–800ms calling an auxiliary LLM judge, the Runwise AutoRouter evaluates lexical and semantic complexity using compiled expressions in under 0.1ms. Simple inquiries are dispatched to Gemini 2.5 Flash, while complex financial disputes and adversarial injection prompts route to Gemini 2.5 Pro.
                </p>

                <div className="mt-6 space-y-3 font-mono text-xs text-slate-300">
                  <div className="flex items-center gap-2.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-orange" />
                    <span>Adversarial jailbreak detection: <code className="text-brand-orange">score = 0.95</code></span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-orange" />
                    <span>High-liability chargeback/dispute keywords: <code className="text-brand-orange">score += 0.50</code></span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-orange" />
                    <span>Multi-entity orders & compound clauses: <code className="text-brand-orange">score += 0.50</code></span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    <span>Decision boundary: <code className="text-emerald-400">score &gt;= 0.45 -&gt; Pro, else Flash</code></span>
                  </div>
                </div>
              </div>

              {/* Wireframe Flow Diagram */}
              <div className="w-full lg:w-1/2 rounded-xl bg-charcoal p-5 border border-surface-border text-xs font-mono">
                <div className="text-slate-400 text-[11px] mb-3 pb-2 border-b border-surface-border flex items-center justify-between">
                  <span>EXECUTION DATAFLOW</span>
                  <span className="text-emerald-400">IN-MEMORY ISOLATION</span>
                </div>

                <div className="space-y-3">
                  <div className="p-2.5 rounded bg-surface border border-surface-border flex items-center justify-between">
                    <span className="text-slate-300">Incoming User Request</span>
                    <span className="text-slate-400">HTTP POST /v1/agent/run</span>
                  </div>
                  <div className="flex justify-center text-slate-600">↓</div>

                  <div className="p-2.5 rounded bg-surface border border-brand-orange/40 flex items-center justify-between">
                    <span className="text-brand-orange">AutoRouter (<code className="text-white">&lt;0.1ms</code>)</span>
                    <span className="text-slate-400">Score vs T=0.45</span>
                  </div>
                  <div className="flex justify-center text-slate-600">↓</div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2.5 rounded bg-surface border border-emerald-500/40 text-center">
                      <div className="text-emerald-400 font-semibold">Gemini 2.5 Flash</div>
                      <div className="text-[10px] text-slate-400 mt-0.5">$0.075 / 1M tokens</div>
                    </div>
                    <div className="p-2.5 rounded bg-surface border border-brand-purple/40 text-center">
                      <div className="text-brand-purple font-semibold">Gemini 2.5 Pro</div>
                      <div className="text-[10px] text-slate-400 mt-0.5">$1.250 / 1M tokens</div>
                    </div>
                  </div>
                  <div className="flex justify-center text-slate-600">↓</div>

                  <div className="p-2.5 rounded bg-surface border border-surface-border flex items-center justify-between">
                    <span className="text-slate-200">Session SandboxDB</span>
                    <span className="text-emerald-400">&lt; 2ms Isolated SQLite</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Reliability Pipeline */}
        {activeTab === "reliability" && (
          <div className="rounded-2xl border border-surface-border bg-surface p-6 sm:p-8 shadow-xl">
            <div className="flex flex-col lg:flex-row gap-8 items-start justify-between">
              <div className="max-w-xl">
                <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-charcoal border border-surface-border text-xs font-mono text-emerald-400 mb-3">
                  <span>Deterministic 4-Tier Grading</span>
                  <span>•</span>
                  <span>CI Regression Gate</span>
                </div>
                <h4 className="text-2xl font-bold text-white tracking-tight">
                  Deterministic Grading & CI Regression Gates
                </h4>
                <p className="mt-3 text-slate-300 text-sm leading-relaxed">
                  Runwise enforces the Precedence Rule: deterministic code and policy checks ALWAYS override subjective LLM judge scores. The automated CI gate (<code className="text-slate-200 font-mono">gate.py</code>) blocks pull requests if task accuracy drops &gt; 2%, latency spikes &gt; 15%, or token consumption inflates &gt; 15%.
                </p>

                <div className="mt-6 grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-lg bg-charcoal border border-surface-border">
                    <span className="text-slate-400">Tier 1: State Auditor</span>
                    <div className="text-slate-200 font-semibold mt-1">SQL Assertions</div>
                    <p className="text-[10px] text-slate-400 mt-1 font-sans">Exact database mutations & tamper audits</p>
                  </div>
                  <div className="p-3 rounded-lg bg-charcoal border border-surface-border">
                    <span className="text-slate-400">Tier 2: Policy Grader</span>
                    <div className="text-slate-200 font-semibold mt-1">Auth Ordering</div>
                    <p className="text-[10px] text-slate-400 mt-1 font-sans">Enforces verify_customer before mutations</p>
                  </div>
                  <div className="p-3 rounded-lg bg-charcoal border border-surface-border">
                    <span className="text-slate-400">Tier 3: Hallucination</span>
                    <div className="text-slate-200 font-semibold mt-1">Regex Grounding</div>
                    <p className="text-[10px] text-slate-400 mt-1 font-sans">Audits factual responses against DB snapshots</p>
                  </div>
                  <div className="p-3 rounded-lg bg-charcoal border border-surface-border">
                    <span className="text-slate-400">Tier 4: Scoped Judge</span>
                    <div className="text-slate-200 font-semibold mt-1">Structured Scoring</div>
                    <p className="text-[10px] text-slate-400 mt-1 font-sans">Tone and polite refusal compliance</p>
                  </div>
                </div>
              </div>

              {/* CI Gate Failure Drill Visual */}
              <div className="w-full lg:w-1/2 rounded-xl bg-charcoal p-5 border border-surface-border text-xs font-mono">
                <div className="text-slate-400 text-[11px] mb-3 pb-2 border-b border-surface-border flex items-center justify-between">
                  <span>CI/CD REGRESSION GATE DRILL</span>
                  <span className="text-red-400">EXIT CODE 1 (BLOCKED)</span>
                </div>

                <div className="space-y-2 text-[11px]">
                  <div className="p-2 rounded bg-surface border border-surface-border flex justify-between">
                    <span className="text-slate-300">Accuracy Threshold</span>
                    <span className="text-red-400">95.0% vs 100.0% (-5.0% DROP)</span>
                  </div>
                  <div className="p-2 rounded bg-surface border border-surface-border flex justify-between">
                    <span className="text-slate-300">Latency Threshold</span>
                    <span className="text-red-400">4,120ms vs 3,063ms (+34.5% SPIKE)</span>
                  </div>
                  <div className="p-2 rounded bg-surface border border-surface-border flex justify-between">
                    <span className="text-slate-300">Token Consumption</span>
                    <span className="text-emerald-400">3,680 vs 3,710 (-0.8% PASS)</span>
                  </div>
                  <div className="p-3 rounded bg-red-950/40 border border-red-500/30 text-red-200 mt-3">
                    [FAIL] CI gate blocked pull request deployment. Candidate accuracy dropped by &gt; 2.0% tolerance. Zero regression policy enforced.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Operations Pipeline */}
        {activeTab === "operations" && (
          <div className="rounded-2xl border border-surface-border bg-surface p-6 sm:p-8 shadow-xl">
            <div className="flex flex-col lg:flex-row gap-8 items-start justify-between">
              <div className="max-w-xl">
                <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-charcoal border border-surface-border text-xs font-mono text-brand-orange mb-3">
                  <span>Canary Sticky Routing</span>
                  <span>•</span>
                  <span>&lt; 200ms Instant Rollback</span>
                </div>
                <h4 className="text-2xl font-bold text-white tracking-tight">
                  Canary Lifecycle, Telemetry & Disaster Recovery
                </h4>
                <p className="mt-3 text-slate-300 text-sm leading-relaxed">
                  Runwise uses cryptographically deterministic session hashing to pin users to prompt variants. If a canary deployment violates the 3,000ms latency SLO, operators execute an instant zero-rebuild rollback in &lt; 200ms with zero container restarts.
                </p>

                <div className="mt-6 space-y-2.5 text-xs font-mono text-slate-300">
                  <div className="flex items-center gap-2">
                    <span className="text-brand-orange">OTel Spans:</span>
                    <span>W3C traceparent distributed context propagation</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-brand-orange">Prometheus:</span>
                    <span>runwise_router_decisions_total, runwise_agent_run_duration</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-brand-orange">Gateway:</span>
                    <span>Mid-flight 429/5xx fallback isolation</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-brand-orange">Recovery:</span>
                    <span>ops/scripts/rollback.py resets weight in &lt; 200ms</span>
                  </div>
                </div>
              </div>

              {/* Operational Drill Terminal View */}
              <div className="w-full lg:w-1/2 rounded-xl bg-charcoal p-5 border border-surface-border text-xs font-mono">
                <div className="text-slate-400 text-[11px] mb-3 pb-2 border-b border-surface-border flex items-center justify-between">
                  <span>TERMINAL: CANARY ROLLBACK DRILL</span>
                  <span className="text-emerald-400">RECOVERED &lt;200MS</span>
                </div>

                <pre className="text-[11px] text-slate-300 overflow-x-auto leading-relaxed">
{`$ python ops/scripts/canary_drill.py
[CANARY] Deployed canary v2.0 at 50% traffic weight
[ANOMALY] Simulated latency breach: 3,420ms (> 3,000ms SLO)
[ALERT] SLO breach detected! Triggering rollback...
$ python ops/scripts/rollback.py --reason "SLO breach"
[OK] Canary disabled. Traffic weight reset to 0.00
[TEST] Testing 10 subsequent customer sessions:
  Session 1-10: 10/10 stable (100% recovered)
[RESULT] Sub-200ms instant rollback verified.`}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
