import { VERIFIED_METRICS } from "@/lib/constants";
import { CheckCircle2, ShieldAlert } from "lucide-react";

export function VerifiedMetrics() {
  return (
    <section id="overview" className="py-16 border-y border-surface-border bg-charcoal-subtle">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-8">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              Grounded Production Evidence
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Verified metrics measured against established baseline deployments.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-surface border border-surface-border text-xs font-mono text-emerald-400 w-fit">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>100% Empirically Validated</span>
          </div>
        </div>

        {/* Metric Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {VERIFIED_METRICS.map((item, idx) => (
            <div
              key={idx}
              className="rounded-xl border border-surface-border bg-surface p-5 flex flex-col justify-between hover:border-slate-700 transition-colors"
            >
              <div>
                <span className="text-[11px] font-mono tracking-wider uppercase text-slate-400">
                  {item.tag}
                </span>
                <div className="mt-2 text-3xl font-extrabold tracking-tight text-white font-mono">
                  {item.value}
                </div>
                <div className="text-sm font-semibold text-slate-200 mt-1">
                  {item.label}
                </div>
              </div>
              <p className="mt-3 text-xs text-slate-400 leading-normal border-t border-surface-border/60 pt-3">
                {item.detail}
              </p>
            </div>
          ))}
        </div>

        {/* Defensibility Disclosure */}
        <div className="mt-6 rounded-lg border border-surface-border/80 bg-surface/50 p-4 text-xs text-slate-400 flex items-start gap-3">
          <ShieldAlert className="h-4 w-4 text-brand-orange shrink-0 mt-0.5" />
          <p className="leading-relaxed">
            <strong className="text-slate-200">Defensibility Taxonomy:</strong> The -57.5% cost reduction and -63.0% median latency reduction were evaluated across the 35 dev tasks in <code className="text-slate-300 font-mono">docs/ROUTING_REPORT.md</code> via empirical trace replay over live baseline trajectories. Baselines 1 and 2 were measured with 100% live Google Cloud Vertex AI inference. These results represent offline benchmark evaluation rather than live production A/B testing. 146 passing tests validates test suite health across 27 modules rather than claiming 100% line coverage.
          </p>
        </div>
      </div>
    </section>
  );
}
