"use client";

import { useState } from "react";
import { PREDEFINED_SCENARIOS } from "@/lib/constants";
import { ScenarioDefinition } from "@/lib/types";
import { Sparkles, ChevronDown, Package, MapPin, RefreshCw, ShieldAlert, Layers } from "lucide-react";

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
  const [showMore, setShowMore] = useState(false);

  // Map to the 4 requested primary compact examples
  const orderLookup = PREDEFINED_SCENARIOS.find((s) => s.id === "scenario_order_lookup");
  const addressUpdate = PREDEFINED_SCENARIOS.find((s) => s.id === "scenario_address_update");
  const refundRequest = PREDEFINED_SCENARIOS.find((s) => s.id === "scenario_refund_request");
  const testSafety = PREDEFINED_SCENARIOS.find((s) => s.id === "scenario_adversarial_injection");
  const multiDispute = PREDEFINED_SCENARIOS.find((s) => s.id === "scenario_multi_order_dispute");

  const primaryExamples = [
    {
      scenario: orderLookup,
      label: "Track an order",
      icon: Package,
    },
    {
      scenario: addressUpdate,
      label: "Change an address",
      icon: MapPin,
    },
    {
      scenario: refundRequest,
      label: "Request a refund",
      icon: RefreshCw,
    },
    {
      scenario: testSafety,
      label: "Test safety",
      icon: ShieldAlert,
    },
  ].filter((item): item is { scenario: ScenarioDefinition; label: string; icon: typeof Package } => Boolean(item.scenario));

  return (
    <div className="w-full mb-6">
      <div className="flex flex-wrap items-center justify-center gap-2">
        <span className="text-xs text-slate-400 font-medium mr-1 hidden sm:inline">
          Try an example:
        </span>

        {primaryExamples.map(({ scenario, label, icon: Icon }) => {
          const isSelected = activeScenarioId === scenario.id;
          return (
            <button
              key={scenario.id}
              disabled={disabled}
              onClick={() => onSelectScenario(scenario)}
              className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium border transition-all active:scale-95 ${
                isSelected
                  ? "bg-brand-orange text-white border-brand-orange shadow-md shadow-brand-orange/20"
                  : "bg-surface border-surface-border text-slate-200 hover:border-brand-orange/40 hover:bg-surface-hover"
              } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <Icon className="h-3.5 w-3.5 opacity-80" />
              <span>{label}</span>
            </button>
          );
        })}

        {/* More Examples Dropdown / Toggle */}
        {multiDispute && (
          <div className="relative">
            <button
              disabled={disabled}
              onClick={() => setShowMore((prev) => !prev)}
              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                activeScenarioId === multiDispute.id
                  ? "bg-brand-orange text-white border-brand-orange"
                  : "bg-surface border-surface-border text-slate-300 hover:text-white hover:border-slate-600"
              }`}
            >
              <Layers className="h-3.5 w-3.5 text-slate-400" />
              <span>More examples</span>
              <ChevronDown className={`h-3 w-3 transition-transform ${showMore ? "rotate-180" : ""}`} />
            </button>

            {showMore && (
              <div className="absolute right-0 sm:left-0 mt-2 w-56 rounded-xl bg-surface border border-surface-border shadow-2xl p-1 z-30 animate-in fade-in zoom-in-95">
                <button
                  onClick={() => {
                    onSelectScenario(multiDispute);
                    setShowMore(false);
                  }}
                  className="w-full text-left px-3 py-2 rounded-lg text-xs font-medium text-slate-200 hover:bg-surface-hover hover:text-white flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-3.5 w-3.5 text-brand-orange" />
                    <span>Multi-order dispute</span>
                  </div>
                  {activeScenarioId === multiDispute.id && (
                    <span className="text-[10px] text-brand-orange font-mono">Active</span>
                  )}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
