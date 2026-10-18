"use client";

import Link from "next/link";
import { ArrowLeft, RotateCcw, History, Sparkles, CheckCircle2 } from "lucide-react";

interface PlaygroundHeaderProps {
  isReplay: boolean;
  onResetSession: () => void;
  onSwitchToLive: () => void;
  isOffline: boolean;
}

export function PlaygroundHeader({
  isReplay,
  onResetSession,
  onSwitchToLive,
  isOffline,
}: PlaygroundHeaderProps) {
  return (
    <header className="border-b border-surface-border bg-charcoal/90 backdrop-blur-md sticky top-0 z-40 py-3 px-4 sm:px-6">
      <div className="mx-auto max-w-4xl flex items-center justify-between gap-4">
        {/* Left: Back & Brand */}
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors py-1 px-2 rounded-md hover:bg-surface"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Landing Page</span>
            <span className="sm:hidden">Back</span>
          </Link>

          <span className="text-slate-600">•</span>

          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-brand-orange shadow-[0_0_6px_#F97316]" />
            <span className="text-sm font-bold text-white tracking-tight">Runwise Playground</span>
          </div>
        </div>

        {/* Right: Clean Mode Indicator & Secondary Reset Action */}
        <div className="flex items-center gap-3">
          {/* Replay vs Live Indicator */}
          {isReplay ? (
            <div className="flex items-center gap-2">
              <span
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/30 cursor-help"
                title="Previously captured, verified execution trace from the 50-task benchmark suite rather than a new model call."
              >
                <History className="h-3 w-3" />
                <span>Recorded Demo</span>
              </span>

              {!isOffline && (
                <button
                  onClick={onSwitchToLive}
                  className="text-xs text-slate-300 hover:text-white underline font-medium transition-colors"
                >
                  Switch to Live
                </button>
              )}
            </div>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Live Inference</span>
            </span>
          )}

          {/* Reset Conversation Button */}
          <button
            onClick={onResetSession}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-surface transition-colors"
            title="Clear conversation history and start fresh"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Reset</span>
          </button>
        </div>
      </div>
    </header>
  );
}
