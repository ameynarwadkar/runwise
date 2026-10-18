import Link from "next/link";
import { ArrowRight, Github } from "lucide-react";
import { PROJECT_METADATA } from "@/lib/constants";

export function HeroSection() {
  return (
    <section className="relative pt-12 pb-10 md:pt-16 md:pb-12 overflow-hidden tech-grid">
      {/* Subtle background glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[300px] bg-brand-orange/10 blur-[130px] pointer-events-none rounded-full" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        {/* Eyebrow */}
        <div className="inline-flex items-center gap-2 rounded-full border border-surface-border bg-surface/80 px-4 py-1.5 text-xs font-mono text-slate-300 shadow-sm mb-6 backdrop-blur">
          <span className="flex h-2 w-2 rounded-full bg-brand-orange" />
          <span className="text-white font-medium">Runwise</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400">AI Agent Reliability Infrastructure</span>
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-4xl mx-auto leading-[1.1]">
          Build agents you can <br className="hidden sm:inline" />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-100 to-slate-400">
            actually trust.
          </span>
        </h1>

        {/* Subtitle - One concise sentence */}
        <p className="mt-5 text-lg sm:text-xl text-slate-300 max-w-2xl mx-auto leading-relaxed font-normal">
          {PROJECT_METADATA.subhead}
        </p>

        {/* CTAs */}
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/demo"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 rounded-lg bg-brand-orange px-6 py-3.5 text-base font-semibold text-white shadow-lg shadow-brand-orange/20 hover:bg-brand-orangeHover transition-all focus:outline-none focus:ring-2 focus:ring-brand-orange/50 active:scale-[0.98]"
          >
            <span>Try Live Demo</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href={PROJECT_METADATA.repoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-lg border border-surface-border bg-surface px-6 py-3.5 text-base font-medium text-slate-200 hover:bg-surface-hover hover:border-slate-600 transition-all focus:outline-none"
          >
            <Github className="h-5 w-5" />
            <span>GitHub</span>
          </Link>
        </div>

        {/* Clean, Minimalist 4-Stage Pipeline: Request → Route → Execute → Evaluate */}
        <div className="mt-12 max-w-3xl mx-auto">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-2 items-center text-center">
            <div className="rounded-xl bg-surface border border-surface-border p-4 flex flex-col items-center">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">Step 1</span>
              <span className="text-base font-bold text-white mt-1">Request</span>
              <span className="text-xs text-slate-400 mt-1">Normalized query</span>
            </div>

            <div className="rounded-xl bg-surface border border-brand-orange/40 p-4 flex flex-col items-center shadow-[0_0_15px_rgba(249,115,22,0.1)]">
              <span className="text-xs font-mono text-brand-orange uppercase tracking-wider font-semibold">Step 2</span>
              <span className="text-base font-bold text-white mt-1">Route</span>
              <span className="text-xs text-brand-orange font-mono mt-1">&lt; 0.1ms CPU</span>
            </div>

            <div className="rounded-xl bg-surface border border-surface-border p-4 flex flex-col items-center">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">Step 3</span>
              <span className="text-base font-bold text-white mt-1">Execute</span>
              <span className="text-xs text-slate-400 mt-1">Sandboxed tools</span>
            </div>

            <div className="rounded-xl bg-surface border border-emerald-500/40 p-4 flex flex-col items-center shadow-[0_0_15px_rgba(16,185,129,0.1)]">
              <span className="text-xs font-mono text-emerald-400 uppercase tracking-wider font-semibold">Step 4</span>
              <span className="text-base font-bold text-white mt-1">Evaluate</span>
              <span className="text-xs text-emerald-400 font-mono mt-1">Deterministic</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
