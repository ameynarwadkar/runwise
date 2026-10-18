import { ShieldCheck } from "lucide-react";

export function VerifiedMetrics() {
  const metrics = [
    {
      value: "50",
      label: "Evaluation Tasks",
      detail: "35 Dev + 15 Frozen Holdout tasks across 4 customer service domains.",
      tag: "Deterministic Evals",
    },
    {
      value: "151 / 151",
      label: "Passing Tests",
      detail: "Platform and API integration test suite across 28 modules with 0 regressions.",
      tag: "Automated Suite",
    },
    {
      value: "-57.5%",
      label: "Modeled Cost Reduction",
      detail: "$3.54 vs. $8.33 / 1k requests under empirical trace replay versus Always Pro.",
      tag: "Trace Replay",
    },
  ];

  return (
    <section id="overview" className="py-14 border-y border-surface-border bg-charcoal-subtle">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {metrics.map((item, idx) => (
            <div
              key={idx}
              className="rounded-2xl border border-surface-border bg-surface p-7 flex flex-col justify-between hover:border-slate-700 transition-colors shadow-sm"
            >
              <div>
                <span className="text-xs font-mono font-semibold tracking-wider uppercase text-brand-orange">
                  {item.tag}
                </span>
                <div className="mt-3 text-4xl sm:text-5xl font-extrabold tracking-tight text-white font-mono">
                  {item.value}
                </div>
                <div className="text-lg font-semibold text-slate-100 mt-2">
                  {item.label}
                </div>
              </div>
              <p className="mt-4 text-sm text-slate-300 leading-relaxed border-t border-surface-border/60 pt-4">
                {item.detail}
              </p>
            </div>
          ))}
        </div>

        {/* Concise factual disclaimer */}
        <p className="mt-8 text-xs text-slate-400 text-center max-w-2xl mx-auto leading-relaxed">
          Cost reduction is estimated via empirical trace replay over baseline trajectories, not production A/B traffic. Test count reflects unit and integration suite health across 28 modules.
        </p>
      </div>
    </section>
  );
}
