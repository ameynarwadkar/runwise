import { ROUTING_BENCHMARK_DATA, PRICING } from "@/lib/constants";
import { TrendingDown, Clock, CheckCircle2, AlertCircle } from "lucide-react";

export function BenchmarkComparison() {
  return (
    <section id="benchmarks" className="py-20 border-t border-surface-border bg-charcoal-subtle">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mb-10">
          <span className="text-xs font-mono uppercase tracking-widest text-brand-orange font-semibold">
            Empirical Evaluation Report
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mt-1">
            Cost-Aware Auto-Routing Benchmark
          </h2>
          <p className="mt-3 text-base text-slate-300 leading-relaxed">
            Frontier reasoning models are essential for high-liability disputes and adversarial jailbreaks, but wasteful for routine queries. Runwise optimizes unit economics under deterministic correctness constraints across 35 benchmark evaluation tasks.
          </p>
        </div>

        {/* Visual Cost & Latency Comparison Card */}
        <div className="mb-10 rounded-2xl border border-surface-border bg-surface p-6 sm:p-8 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-surface-border gap-3">
            <div>
              <span className="text-xs font-mono uppercase tracking-wider text-brand-orange font-semibold">
                Head-to-Head Comparison
              </span>
              <h3 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-0.5">
                Always Strong Baseline vs. Runwise AutoRouter
              </h3>
            </div>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-charcoal border border-surface-border text-xs font-mono font-medium text-slate-300">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>35 Benchmark Tasks • 100% Pass Rate Retained</span>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-6">
            {/* Always Pro Baseline */}
            <div className="rounded-xl bg-charcoal p-5 border border-surface-border flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-300">Always Strong (Gemini 2.5 Pro)</span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">Baseline</span>
                </div>
                <div className="mt-4 flex items-baseline gap-3">
                  <span className="text-3xl font-extrabold text-white font-mono">$8.33</span>
                  <span className="text-sm text-slate-400 font-mono">/ 1,000 requests</span>
                </div>
                {/* Cost Bar */}
                <div className="mt-3">
                  <div className="flex justify-between text-xs font-mono text-slate-400 mb-1">
                    <span>Token Cost Index</span>
                    <span>100% Baseline</span>
                  </div>
                  <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-slate-500 rounded-full w-full" />
                  </div>
                </div>

                {/* Latency Bar */}
                <div className="mt-4">
                  <div className="flex justify-between text-xs font-mono text-slate-400 mb-1">
                    <span>Median Latency (p50)</span>
                    <span className="text-slate-300 font-semibold">10.33s</span>
                  </div>
                  <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-slate-500 rounded-full w-full" />
                  </div>
                </div>
              </div>

              <p className="mt-5 text-sm text-slate-400 border-t border-surface-border pt-3">
                Frontier pricing applied uniformly to every request. 100% of volume incurs 16.6x pricing premium regardless of task complexity.
              </p>
            </div>

            {/* Runwise Adaptive Router */}
            <div className="rounded-xl bg-charcoal p-5 border border-brand-orange/40 flex flex-col justify-between shadow-[0_0_20px_rgba(249,115,22,0.1)]">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-white flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-brand-orange animate-pulse" />
                    Adaptive Semantic Router (Runwise)
                  </span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-brand-orange/20 text-brand-orange border border-brand-orange/40 font-semibold">Active Strategy</span>
                </div>
                <div className="mt-4 flex items-baseline gap-3">
                  <span className="text-3xl font-extrabold text-brand-orange font-mono">$3.54</span>
                  <span className="text-sm text-slate-300 font-mono">/ 1,000 requests</span>
                  <span className="text-xs font-bold font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    -57.5% Cost
                  </span>
                </div>

                {/* Cost Bar */}
                <div className="mt-3">
                  <div className="flex justify-between text-xs font-mono text-slate-300 mb-1">
                    <span>Token Cost Index</span>
                    <span className="text-emerald-400 font-semibold">42.5% of Baseline (-57.5%)</span>
                  </div>
                  <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-brand-orange to-emerald-400 rounded-full w-[42.5%]" />
                  </div>
                </div>

                {/* Latency Bar */}
                <div className="mt-4">
                  <div className="flex justify-between text-xs font-mono text-slate-300 mb-1">
                    <span>Median Latency (p50)</span>
                    <span className="text-emerald-400 font-semibold">3.82s (2.7x Faster / -63.0%)</span>
                  </div>
                  <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-400 rounded-full w-[37.0%]" />
                  </div>
                </div>
              </div>

              <p className="mt-5 text-sm text-slate-300 border-t border-surface-border pt-3">
                Offloads 65.7% of volume to Flash (<code className="text-white font-mono">&lt;0.1ms</code> classifier), while reserving Pro for adversarial and financial dispute edge cases with 100% accuracy.
              </p>
            </div>
          </div>
        </div>

        {/* 4-Way Comparison Table */}
        <div className="rounded-xl border border-surface-border bg-surface overflow-hidden shadow-xl">
          <div className="p-4 sm:p-5 border-b border-surface-border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <span className="font-mono text-sm text-white font-semibold uppercase tracking-wider">
                Full 4-Way Strategy Benchmark (35 Stratified Tasks)
              </span>
              <p className="text-xs text-slate-400 mt-0.5">
                Pass rates measured under deterministic SQL assertions, trajectory policy checks, and hallucination audits.
              </p>
            </div>
            <span className="text-xs text-brand-orange font-mono">
              Source: docs/ROUTING_REPORT.md
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm font-mono">
              <thead className="bg-charcoal text-slate-300 border-b border-surface-border uppercase tracking-wider text-xs">
                <tr>
                  <th className="py-3.5 px-4 sm:px-6">Strategy</th>
                  <th className="py-3.5 px-4">Methodology</th>
                  <th className="py-3.5 px-4 text-center">Task Accuracy</th>
                  <th className="py-3.5 px-4 text-right">Cost / 1k</th>
                  <th className="py-3.5 px-4 text-right">vs. Pro Cost</th>
                  <th className="py-3.5 px-4 text-right">p50 Latency</th>
                  <th className="py-3.5 px-4 text-right">p95 Latency</th>
                  <th className="py-3.5 px-4 sm:px-6 text-right">Traffic Split</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {ROUTING_BENCHMARK_DATA.map((row, idx) => (
                  <tr
                    key={idx}
                    className={`hover:bg-surface-hover/70 transition-colors ${
                      row.isRecommended
                        ? "bg-brand-orange/10 font-bold text-white"
                        : "text-slate-200"
                    }`}
                  >
                    <td className="py-3.5 px-4 sm:px-6 flex items-center gap-2">
                      <span>{row.strategy}</span>
                      {row.isRecommended && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-brand-orange/20 text-brand-orange border border-brand-orange/40 font-semibold">
                          Active
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`inline-flex px-2.5 py-0.5 rounded text-xs font-medium ${
                          row.methodology === "Live Vertex AI"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-slate-800 text-slate-300 border border-slate-700"
                        }`}
                      >
                        {row.methodology}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center text-emerald-400 font-semibold">
                      {row.accuracy}
                    </td>
                    <td className="py-3.5 px-4 text-right text-white font-bold">
                      {row.costPer1k}
                    </td>
                    <td
                      className={`py-3.5 px-4 text-right ${
                        row.vsProCostDelta.startsWith("-")
                          ? "text-emerald-400 font-bold"
                          : row.vsProCostDelta === "Baseline"
                          ? "text-slate-400"
                          : "text-amber-400"
                      }`}
                    >
                      {row.vsProCostDelta}
                    </td>
                    <td className="py-3.5 px-4 text-right text-slate-100">
                      {row.p50Latency}
                    </td>
                    <td className="py-3.5 px-4 text-right text-slate-300">
                      {row.p95Latency}
                    </td>
                    <td className="py-3.5 px-4 sm:px-6 text-right text-slate-200">
                      {row.trafficSplit}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Pricing Ratio & Technical Footnotes */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-5 text-sm text-slate-300">
          <div className="rounded-xl bg-surface border border-surface-border p-5">
            <h4 className="font-bold text-white flex items-center gap-2 font-mono text-base mb-2">
              <span className="text-brand-orange">■</span> Model Economics & 16.6x Price Spread
            </h4>
            <p className="text-slate-300 leading-relaxed">
              Google Cloud Vertex AI standard pricing: <strong>Gemini 2.5 Flash</strong> costs ${PRICING.flash.inputPerMillion}/1M input vs. <strong>Gemini 2.5 Pro</strong> at ${PRICING.pro.inputPerMillion}/1M input. Deploying Pro across routine read-only queries inflates unit economics without delivering higher task accuracy.
            </p>
          </div>

          <div className="rounded-xl bg-surface border border-surface-border p-5">
            <h4 className="font-bold text-white flex items-center gap-2 font-mono text-base mb-2">
              <span className="text-brand-orange">■</span> The Anti-Pattern of Auxiliary LLM Routers
            </h4>
            <p className="text-slate-300 leading-relaxed">
              Standard routing designs call an auxiliary &quot;router LLM&quot; to classify incoming prompts, incurring 300–800ms of latency and consuming tokens before the agent starts. Runwise evaluates lexical and semantic complexity on CPU in &lt; 0.1ms with zero LLM invocation overhead.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
