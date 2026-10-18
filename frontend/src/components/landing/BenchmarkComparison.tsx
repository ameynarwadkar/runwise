"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { ROUTING_BENCHMARK_DATA } from "@/lib/constants";

export function BenchmarkComparison() {
  const [showFullTable, setShowFullTable] = useState(false);

  return (
    <section id="benchmarks" className="py-16 border-t border-surface-border bg-charcoal-subtle">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-10">
          <span className="text-xs font-mono uppercase tracking-widest text-brand-orange font-semibold">
            Empirical Benchmark
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mt-1">
            Cost & Latency Optimization
          </h2>
          <p className="mt-3 text-base text-slate-300 leading-relaxed">
            Runwise dynamically routes routine customer requests to Gemini Flash while reserving Pro for high-liability edge cases.
          </p>
        </div>

        {/* Prominent Two-Bar Head-to-Head Comparison */}
        <div className="rounded-2xl border border-surface-border bg-surface p-7 sm:p-9 shadow-xl">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
            {/* Always Pro Baseline */}
            <div className="rounded-xl bg-charcoal p-6 border border-surface-border flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-300">Always Strong (Gemini 2.5 Pro)</span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">Baseline</span>
                </div>
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold text-white font-mono">$8.33</span>
                  <span className="text-sm text-slate-400 font-mono">/ 1,000 requests</span>
                </div>

                {/* Relative Cost Bar */}
                <div className="mt-4">
                  <div className="flex justify-between text-xs font-mono text-slate-400 mb-1.5">
                    <span>Relative Cost Index</span>
                    <span>100%</span>
                  </div>
                  <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-slate-500 rounded-full w-full" />
                  </div>
                </div>

                <div className="mt-4 text-xs font-mono text-slate-400 flex justify-between">
                  <span>Median Latency (p50):</span>
                  <span className="text-slate-200 font-semibold">10.33s</span>
                </div>
              </div>
            </div>

            {/* Runwise AutoRouter */}
            <div className="rounded-xl bg-charcoal p-6 border border-brand-orange/40 flex flex-col justify-between shadow-[0_0_20px_rgba(249,115,22,0.1)]">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-white flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-brand-orange" />
                    Adaptive Semantic Router (Runwise)
                  </span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-brand-orange/20 text-brand-orange font-semibold">Active</span>
                </div>
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold text-brand-orange font-mono">$3.54</span>
                  <span className="text-sm text-slate-300 font-mono">/ 1,000 requests</span>
                  <span className="text-xs font-bold font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 ml-2">
                    -57.5%
                  </span>
                </div>

                {/* Relative Cost Bar */}
                <div className="mt-4">
                  <div className="flex justify-between text-xs font-mono text-slate-300 mb-1.5">
                    <span>Relative Cost Index</span>
                    <span className="text-emerald-400 font-semibold">42.5% (-57.5% Cost)</span>
                  </div>
                  <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-brand-orange to-emerald-400 rounded-full w-[42.5%]" />
                  </div>
                </div>

                <div className="mt-4 text-xs font-mono text-slate-300 flex justify-between">
                  <span>Median Latency (p50):</span>
                  <span className="text-emerald-400 font-semibold">3.82s (2.7x faster)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Footnote & Methodology Link */}
          <div className="mt-6 pt-5 border-t border-surface-border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs text-slate-400">
            <p className="leading-relaxed">
              Cost and latency figures are empirical trace-replay estimates evaluated across 35 benchmark dev tasks under identical task accuracy constraints.
            </p>
            <div className="flex items-center gap-4 shrink-0">
              <Link
                href="https://github.com/ameynarwadkar/runwise/blob/main/docs/ROUTING_REPORT.md"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-slate-300 hover:text-brand-orange font-medium transition-colors"
              >
                <span>View full methodology</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </Link>
              <button
                onClick={() => setShowFullTable((prev) => !prev)}
                className="inline-flex items-center gap-1 text-slate-300 hover:text-white font-medium transition-colors"
              >
                <span>{showFullTable ? "Hide table" : "Show 4-way table"}</span>
                {showFullTable ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          {/* Optional Collapsible 4-Way Technical Table */}
          {showFullTable && (
            <div className="mt-6 pt-6 border-t border-surface-border overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="text-slate-400 border-b border-surface-border uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-2.5 px-3">Strategy</th>
                    <th className="py-2.5 px-3">Methodology</th>
                    <th className="py-2.5 px-3 text-right">Cost / 1k</th>
                    <th className="py-2.5 px-3 text-right">vs. Pro</th>
                    <th className="py-2.5 px-3 text-right">p50 Latency</th>
                    <th className="py-2.5 px-3 text-right">Traffic Split</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {ROUTING_BENCHMARK_DATA.map((row, idx) => (
                    <tr
                      key={idx}
                      className={row.isRecommended ? "text-white font-bold bg-brand-orange/5" : "text-slate-300"}
                    >
                      <td className="py-2.5 px-3">{row.strategy}</td>
                      <td className="py-2.5 px-3 text-slate-400">{row.methodology}</td>
                      <td className="py-2.5 px-3 text-right text-white font-semibold">{row.costPer1k}</td>
                      <td className={`py-2.5 px-3 text-right ${row.vsProCostDelta.startsWith("-") ? "text-emerald-400 font-semibold" : "text-slate-400"}`}>
                        {row.vsProCostDelta}
                      </td>
                      <td className="py-2.5 px-3 text-right">{row.p50Latency}</td>
                      <td className="py-2.5 px-3 text-right text-slate-400">{row.trafficSplit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
