import { SanitizedTimelineEvent } from "@/lib/types";
import { Clock, Cpu, ShieldCheck, Terminal, Bot, ArrowDown } from "lucide-react";

interface ExecutionTimelineProps {
  events: SanitizedTimelineEvent[];
}

export function ExecutionTimeline({ events }: ExecutionTimelineProps) {
  if (!events || events.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-slate-400">
        No execution trace recorded yet. Run a query to inspect live telemetry.
      </div>
    );
  }

  const getEventBadge = (type: string) => {
    switch (type) {
      case "REQUEST_RECEIVED":
        return { label: "01 REQUEST", color: "text-slate-400 border-slate-700 bg-slate-800" };
      case "ROUTING_DECISION":
        return { label: "02 ROUTER", color: "text-brand-orange border-brand-orange/30 bg-brand-orange/10" };
      case "MODEL_INVOCATION":
        return { label: "03 MODEL", color: "text-brand-purple border-brand-purple/30 bg-brand-purple/10" };
      case "TOOL_EXECUTION":
        return { label: "04 TOOL", color: "text-blue-400 border-blue-500/30 bg-blue-500/10" };
      case "FINAL_RESPONSE":
        return { label: "05 ANSWER", color: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" };
      case "EVALUATION":
        return { label: "06 EVAL", color: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" };
      default:
        return { label: type, color: "text-slate-400 border-slate-700 bg-slate-800" };
    }
  };

  return (
    <div className="p-4 space-y-3 font-mono text-xs">
      {events.map((ev, idx) => {
        const badge = getEventBadge(ev.event_type);
        return (
          <div
            key={idx}
            className="rounded-lg border border-surface-border bg-charcoal p-3 space-y-2 relative"
          >
            <div className="flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badge.color}`}>
                  {badge.label}
                </span>
                <span className="text-slate-300 font-semibold">{ev.event_type}</span>
              </div>
              <span className="text-[10px] text-slate-400">
                {ev.timestamp_iso ? new Date(ev.timestamp_iso).toLocaleTimeString() : `Step ${ev.seq}`}
              </span>
            </div>

            <p className="text-slate-300 font-sans text-xs leading-relaxed">
              {ev.summary}
            </p>

            {ev.details && Object.keys(ev.details).length > 0 && (
              <div className="bg-surface p-2 rounded border border-surface-border/60 text-[10px] text-slate-400 overflow-x-auto">
                <pre>{JSON.stringify(ev.details, null, 2)}</pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
