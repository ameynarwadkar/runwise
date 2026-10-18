"use client";

import { PREDEFINED_SCENARIOS } from "@/lib/constants";
import { ScenarioDefinition } from "@/lib/types";
import { Zap, ShieldCheck, CornerDownRight } from "lucide-react";

interface ScenarioSelectorProps {
  activeScenarioId: string | null;
  onSelectScenario: (scenario: ScenarioDefinition) => void;
  disabled?: boolean;
}

export function ScenarioSelector({
  activeScenarioId,
  onSelectScenario,
  disabled,
}: ScenarioSelectorProps) {
  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400">
          Pre-Seeded Ground-Truth Scenarios
        </span>
        <span className="text-[11px] font-mono text-slate-400">
          Evaluated via Tiers 1–3
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-2.5">
        {PREDEFINED_SCENARIOS.map((scenario) => {
          const isSelected = activeScenarioId === scenario.id;
          return (
            <button
              key={scenario.id}
              disabled={disabled}
              onClick={() => onSelectScenario(scenario)}
              className={`rounded-lg p-3 text-left border transition-all flex flex-col justify-between ${
                isSelected
                  ? "bg-surface-active border-brand-orange/60 shadow-[0_0_10px_rgba(249,115,22,0.12)]"
                  : "bg-surface border-surface-border hover:border-slate-700 hover:bg-surface-hover"
              } ${disabled ? "opacity-60 cursor-not-allowed" : ""}`}
            >
              <div>
                <div className="flex items-center justify-between gap-1 mb-1.5">
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded font-medium ${
                      scenario.expected_tier === "flash"
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        : "bg-purple-500/10 text-brand-purple border border-purple-500/20"
                    }`}
                  >
                    {scenario.badge}
                  </span>
                  <span className="text-[10px] font-mono text-slate-400">
                    {scenario.task_id}
                  </span>
                </div>
                <div className="text-xs font-bold text-white leading-snug">
                  {scenario.title}
                </div>
                <p className="mt-1 text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                  {scenario.description}
                </p>
              </div>

              <div className="mt-2.5 pt-2 border-t border-surface-border/50 flex items-center justify-between text-[10px] font-mono text-slate-400">
                <span>Load Scenario</span>
                <CornerDownRight className="h-3 w-3 text-brand-orange" />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
