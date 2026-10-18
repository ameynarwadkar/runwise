import { SanitizedToolCall } from "@/lib/types";
import { Wrench, CheckCircle2, XCircle } from "lucide-react";

interface ToolCallsViewProps {
  toolCalls: SanitizedToolCall[];
}

export function ToolCallsView({ toolCalls }: ToolCallsViewProps) {
  if (!toolCalls || toolCalls.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-slate-400">
        No tool calls executed for this turn. (Direct response or polite policy refusal).
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4 text-xs font-mono">
      {toolCalls.map((tc, idx) => (
        <div
          key={idx}
          className="rounded-lg border border-surface-border bg-charcoal p-3.5 space-y-2.5"
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-2 border-b border-surface-border/60">
            <div className="flex items-center gap-2">
              <Wrench className="h-3.5 w-3.5 text-brand-orange" />
              <span className="font-bold text-white text-[13px]">{tc.tool_name}</span>
            </div>
            <div className="flex items-center gap-1.5">
              {tc.status === "success" ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>SUCCESS</span>
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 font-semibold">
                  <XCircle className="h-3 w-3" />
                  <span>ERROR</span>
                </span>
              )}
            </div>
          </div>

          {/* Input Arguments */}
          <div>
            <div className="text-[10px] uppercase text-slate-400 font-semibold mb-1">
              Arguments (Input)
            </div>
            <div className="bg-surface p-2.5 rounded border border-surface-border/60 text-slate-300 overflow-x-auto text-[11px]">
              <pre>{JSON.stringify(tc.arguments, null, 2)}</pre>
            </div>
          </div>

          {/* Output Result Data */}
          <div>
            <div className="text-[10px] uppercase text-slate-400 font-semibold mb-1">
              Sandbox Result (Output)
            </div>
            {tc.result_data ? (
              <div className="bg-surface p-2.5 rounded border border-surface-border/60 text-slate-300 overflow-x-auto text-[11px]">
                <pre>{JSON.stringify(tc.result_data, null, 2)}</pre>
              </div>
            ) : tc.error_message ? (
              <div className="bg-red-950/30 p-2.5 rounded border border-red-500/30 text-red-300 text-[11px]">
                {tc.error_message}
              </div>
            ) : (
              <div className="text-slate-400 text-[11px]">No return payload.</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
