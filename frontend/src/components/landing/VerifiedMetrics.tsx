import { VERIFIED_METRICS } from "@/lib/constants";
import { CheckCircle2, ShieldAlert } from "lucide-react";

export function VerifiedMetrics() {
  return (
    <section id="overview" className="py-16 border-y border-surface-border bg-charcoal-subtle">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              Grounded Production Evidence
            </h2>
            <p className="text-sm text-slate-300 mt-1">
              Verified metrics measured against established baselines under strict evaluation invariants.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md bg-surface border border-surface-border text-xs font-mono font-medium text-emerald-400 w-fit">
            <CheckCircle2 className="h-4 w-4" />
            <span>50 Evaluated Tasks Validated</span>
          </div>
        </div>

        {/* Metric Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {VERIFIED_METRICS.map((item, idx) => (
            <div
              key={idx}
              className="rounded-xl border border-surface-border bg-surface p-5 flex flex-col justify-between hover:border-slate-700 transition-colors shadow-sm"
            >
              <div>
                <span className="text-xs font-mono font-semibold tracking-wider uppercase text-brand-orange/90">
                  {item.tag}
                </span>
                <div className="mt-2 text-3xl font-extrabold tracking-tight text-white font-mono">
                  {item.value}
                </div>
                <div className="text-base font-semibold text-slate-100 mt-1">
                  {item.label}
                </div>
              </div>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed border-t border-surface-border/60 pt-3">
                {item.detail}
              </p>
            </div>
          ))}
        </div>

        {/* Defensibility Disclosure */}
        <div className="mt-6 rounded-lg border border-surface-border/80 bg-surface/50 p-4 text-sm text-slate-300 flex items-start gap-3">
          <ShieldAlert className="h-5 w-5 text-brand-orange shrink-0 mt-0.5" />
          <p className="leading-relaxed">
            <strong className="text-slate-100">Defensibility Taxonomy:</strong> The 100.0% pass rate reflects exact evaluation over the 50 registered benchmark tasks (150 trials) under deterministic SQL assertions, trajectory policy checks, and regex audits—it is not an assertion of universal reliability across arbitrary open-ended tasks. The -57.5% cost reduction and -63.0% median latency reduction were evaluated across 35 dev tasks in <code className="text-brand-orange font-mono">docs/ROUTING_REPORT.md</code> via empirical trace replay over live baseline trajectories. All 151 unit and integration tests validate platform and API correctness across 28 modules.
          </p>
        </div>
      </div>
    </section>
  );
}
