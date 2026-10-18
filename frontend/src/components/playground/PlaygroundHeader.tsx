"use client";

import Link from "next/link";
import { ArrowLeft, RotateCcw, Copy, Check, ShieldCheck, History } from "lucide-react";
import { useState } from "react";

interface PlaygroundHeaderProps {
  sessionId: string;
  isReplay: boolean;
  onResetSession: () => void;
  onToggleReplayMode: () => void;
  isOffline: boolean;
}

export function PlaygroundHeader({
  sessionId,
  isReplay,
  onResetSession,
  onToggleReplayMode,
  isOffline,
}: PlaygroundHeaderProps) {
  const [copied, setCopied] = useState(false);

  const copySession = () => {
    navigator.clipboard.writeText(sessionId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <header className="border-b border-surface-border bg-charcoal-subtle py-3 px-4 sm:px-6">
      <div className="mx-auto max-w-7xl flex flex-wrap items-center justify-between gap-3">
        {/* Left: Back & Title */}
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors py-1 px-2 rounded-md hover:bg-surface"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Landing Page</span>
          </Link>

          <span className="text-slate-600">/</span>

          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-brand-orange" />
            <h1 className="text-sm font-bold text-white tracking-tight">Runwise Playground</h1>
          </div>

          {/* Mode Pill */}
          <span
            className={`text-[11px] font-mono px-2.5 py-0.5 rounded-full border ${
              isReplay
                ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
            }`}
          >
            {isReplay ? "VERIFIED REPLAY MODE" : "LIVE BACKEND MODE"}
          </span>

          {isOffline && !isReplay && (
            <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/30">
              Offline (Replay Active)
            </span>
          )}
        </div>

        {/* Right: Session ID & Actions */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Session ID Pill */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface border border-surface-border text-xs font-mono text-slate-300">
            <span className="text-slate-400">Session:</span>
            <span className="text-white">{sessionId.slice(0, 14)}...</span>
            <button
              onClick={copySession}
              className="text-slate-400 hover:text-white transition-colors ml-1"
              title="Copy Session ID"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            </button>
          </div>

          {/* Replay Toggle Button */}
          <button
            onClick={onToggleReplayMode}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md border text-xs font-medium transition-colors ${
              isReplay
                ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                : "bg-surface border-surface-border text-slate-300 hover:bg-surface-hover hover:text-white"
            }`}
          >
            <History className="h-3.5 w-3.5" />
            <span>{isReplay ? "Exit Replay" : "Replay Mode"}</span>
          </button>

          {/* Reset Session Button */}
          <button
            onClick={onResetSession}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-surface border border-surface-border text-xs font-medium text-slate-300 hover:bg-surface-hover hover:text-white transition-colors"
            title="Wipe active session and initialize fresh in-memory sandbox"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Reset</span>
          </button>
        </div>
      </div>
    </header>
  );
}
