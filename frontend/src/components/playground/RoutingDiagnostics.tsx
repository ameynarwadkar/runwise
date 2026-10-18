import { Zap, Cpu, Gauge, AlertCircle } from "lucide-react";

interface RoutingDiagnosticsProps {
  model?: string;
  complexityScore?: number | null;
  routingReason?: string | null;
  featuresDetected?: string[];
}

export function RoutingDiagnostics({
  model,
  complexityScore,
  routingReason,
  featuresDetected,
}: RoutingDiagnosticsProps) {
  const score = complexityScore ?? 0.0;
  const isPro = score >= 0.45;

  return (
    <div className="p-4 space-y-4 font-mono text-xs">
      {/* Model Tier Card */}
      <div className="rounded-lg border border-surface-border bg-charcoal p-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-slate-400 text-[11px] uppercase">Selected Model Tier</span>
          <span
            className={`px-2.5 py-0.5 rounded text-xs font-bold font-mono border ${
              isPro
                ? "bg-purple-500/15 text-brand-purple border-purple-500/30"
                : "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
            }`}
          >
            {model ? model.replace("vertex_ai/", "") : isPro ? "gemini-2.5-pro" : "gemini-2.5-flash"}
          </span>
        </div>
        <p className="text-slate-300 font-sans text-xs">
          {routingReason || "AutoRouter dynamically resolved target model tier."}
        </p>
      </div>

      {/* Complexity Meter */}
      <div className="rounded-lg border border-surface-border bg-charcoal p-4 space-y-3">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-slate-400 uppercase">Complexity Score Meter</span>
          <div className="flex items-center gap-1.5 font-bold">
            <span className="text-white">{score.toFixed(2)}</span>
            <span className="text-slate-500">/ 1.00</span>
          </div>
        </div>

        {/* Visual Progress Bar with Threshold Marker */}
        <div className="relative h-3 w-full rounded-full bg-surface border border-surface-border overflow-hidden">
          <div
            className={`h-full transition-all duration-500 rounded-full ${
              isPro ? "bg-brand-purple" : "bg-emerald-400"
            }`}
            style={{ width: `${Math.min(100, Math.max(0, score * 100))}%` }}
          />
          {/* Threshold line at 45% */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-brand-orange z-10"
            style={{ left: "45%" }}
            title="Threshold T=0.45"
          />
        </div>

        <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
          <span>0.00 (Flash / Simple)</span>
          <span className="text-brand-orange font-semibold">T = 0.45</span>
          <span>1.00 (Pro / High Risk)</span>
        </div>
      </div>

      {/* Detected Feature Vectors */}
      <div className="rounded-lg border border-surface-border bg-charcoal p-4 space-y-2.5">
        <span className="text-slate-400 text-[11px] uppercase">
          Semantic Feature Vectors Detected
        </span>
        <div className="flex flex-wrap gap-1.5 pt-1">
          {featuresDetected && featuresDetected.length > 0 ? (
            featuresDetected.map((feat, idx) => (
              <span
                key={idx}
                className="px-2 py-1 rounded bg-surface border border-brand-orange/30 text-brand-orange text-[10px]"
              >
                +{feat}
              </span>
            ))
          ) : (
            <span className="text-slate-400 text-[11px]">
              No high-risk vectors detected (Routine standard inquiry).
            </span>
          )}
        </div>
      </div>

      {/* Zero Overhead Note */}
      <div className="p-3 rounded bg-surface border border-surface-border text-[11px] text-slate-400 leading-relaxed font-sans">
        <span className="text-brand-orange font-mono font-semibold">Sub-0.1ms Engine: </span>
        Routing is calculated purely on CPU via pre-compiled structural regular expressions, consuming 0 tokens and avoiding auxiliary LLM latency.
      </div>
    </div>
  );
}
