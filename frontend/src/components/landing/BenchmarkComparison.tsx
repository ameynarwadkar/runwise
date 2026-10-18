import { ROUTING_BENCHMARK_DATA, PRICING } from "@/lib/constants";
import { TrendingDown, Clock, CheckCircle2, AlertCircle } from "lucide-react";

export function BenchmarkComparison() {
  return (
    <section id="benchmarks" className="py-20 border-t border-surface-border bg-charcoal-subtle">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mb-12">
          <span className="text-xs font-mono uppercase tracking-widest text-brand-orange">
            Empirical Evaluation Report
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mt-1">
            Cost-Aware Auto-Routing Benchmark
          </h2>
          <p className="mt-3 text-base text-slate-400 leading-relaxed">
            Frontier models are essential for high-liability legal disputes and adversarial injections, but wasteful for simple tracking. Runwise balances unit economics with safety invariants across 35 benchmark tasks.
          </p>
        </div>

        {/* Highlight Callouts */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          <div className="rounded-xl border border-brand-orange/30 bg-surface p-5 shadow-[0_0_15px_rgba(249,115,22,0.06)]">
            <div className="flex items-center gap-2 text-brand-orange text-xs font-mono font-semibold">
              <TrendingDown className="h-4 w-4" />
              <span>-57.5% COST VS. PRO</span>
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-white">$3.54 / 1k</div>
            <p className="mt-1 text-xs text-slate-400">
              Down from $8.33 / 1k (Always-Pro baseline), saving 57.5% under empirical trace replay.
            </p>
          </div>

          <div className="rounded-xl border border-emerald-500/30 bg-surface p-5 shadow-[0_0_15px_rgba(16,185,129,0.06)]">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-mono font-semibold">
              <Clock className="h-4 w-4" />
              <span>-63.0% MEDIAN LATENCY</span>
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-white">3.82s p50</div>
            <p className="mt-1 text-xs text-slate-400">
              Down from 10.33s p50 (Always-Pro baseline), accelerating customer response speed by 2.7x.
            </p>
          </div>

          <div className="rounded-xl border border-surface-border bg-surface p-5">
            <div className="flex items-center gap-2 text-slate-300 text-xs font-mono font-semibold">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>100% ACCURACY RETAINED</span>
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-white">100.0% Pass</div>
            <p className="mt-1 text-xs text-slate-400">
              Maintained across all 35 dev tasks, offloading 65.7% of query volume to Flash without policy regressions.
            </p>
          </div>
        </div>

        {/* 4-Way Comparison Table */}
        <div className="rounded-xl border border-surface-border bg-surface overflow-hidden shadow-xl">
          <div className="p-4 sm:p-5 border-b border-surface-border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <span className="font-mono text-xs text-slate-300 font-semibold uppercase tracking-wider">
              4-Way Strategy Benchmark (35 Stratified Tasks)
            </span>
            <span className="text-xs text-slate-500 font-mono">
              Source: docs/ROUTING_REPORT.md
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-charcoal text-slate-400 border-b border-surface-border uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3.5 px-4 sm:px-6">Strategy</th>
                  <th className="py-3.5 px-4">Methodology</th>
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
                        ? "bg-brand-orange/5 font-semibold text-white"
                        : "text-slate-300"
                    }`}
                  >
                    <td className="py-3.5 px-4 sm:px-6 flex items-center gap-2">
                      <span>{row.strategy}</span>
                      {row.isRecommended && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-orange/20 text-brand-orange border border-brand-orange/30">
                          Active
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-[10px] ${
                          row.methodology === "Live Vertex AI"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-slate-800 text-slate-400 border border-slate-700"
                        }`}
                      >
                        {row.methodology}
                      </span>
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
                    <td className="py-3.5 px-4 text-right text-slate-200">
                      {row.p50Latency}
                    </td>
                    <td className="py-3.5 px-4 text-right text-slate-400">
                      {row.p95Latency}
                    </td>
                    <td className="py-3.5 px-4 sm:px-6 text-right text-slate-300">
                      {row.trafficSplit}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Pricing Ratio & LLM Overhead Explanation */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-5 text-xs text-slate-300">
          <div className="rounded-lg bg-surface border border-surface-border p-4">
            <h4 className="font-semibold text-white flex items-center gap-1.5 font-mono text-sm mb-2">
              <span className="text-brand-orange">■</span> Model Economics & 16.6x Pricing Spread
            </h4>
            <p className="text-slate-400 leading-relaxed">
              Google Cloud Vertex AI rates: <strong>Gemini 2.5 Flash</strong> costs ${PRICING.flash.inputPerMillion}/1M input vs. <strong>Gemini 2.5 Pro</strong> at ${PRICING.pro.inputPerMillion}/1M input. Deploying Pro across routine inquiries burns unit economics without improving resolution accuracy.
            </p>
          </div>

          <div className="rounded-lg bg-surface border border-surface-border p-4">
            <h4 className="font-semibold text-white flex items-center gap-1.5 font-mono text-sm mb-2">
              <span className="text-brand-orange">■</span> The Anti-Pattern of Auxiliary LLM Routers
            </h4>
            <p className="text-slate-400 leading-relaxed">
              Many routing systems invoke a &quot;small LLM&quot; to classify requests, incurring 300–800ms of latency and consuming 100+ tokens before the agent starts. Runwise classifies complexity on CPU in &lt; 0.1ms with zero LLM overhead.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
