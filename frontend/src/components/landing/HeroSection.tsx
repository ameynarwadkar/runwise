import Link from "next/link";
import { ArrowRight, Github, ShieldCheck, Zap, Cpu, Terminal } from "lucide-react";
import { PROJECT_METADATA } from "@/lib/constants";

export function HeroSection() {
  return (
    <section className="relative pt-10 pb-8 md:pt-14 md:pb-10 overflow-hidden tech-grid">
      {/* Background glow overlay */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-brand-orange/10 blur-[130px] pointer-events-none rounded-full" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        {/* Eyebrow */}
        <div className="inline-flex items-center gap-2 rounded-full border border-surface-border bg-surface/80 px-4 py-1.5 text-xs font-mono text-slate-300 shadow-sm mb-5 backdrop-blur">
          <span className="flex h-2 w-2 rounded-full bg-brand-orange animate-pulse" />
          <span className="text-brand-orange font-semibold">Runwise v0.1</span>
          <span className="text-slate-500">|</span>
          <span>{PROJECT_METADATA.eyebrow}</span>
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-4xl mx-auto leading-[1.1]">
          Build agents you can <br className="hidden sm:inline" />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-100 to-slate-400">
            actually trust.
          </span>
        </h1>

        {/* Subtitle */}
        <p className="mt-5 text-lg sm:text-xl text-slate-300 max-w-2xl mx-auto leading-relaxed font-normal">
          {PROJECT_METADATA.subhead}
        </p>

        {/* CTAs */}
        <div className="mt-7 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/demo"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 rounded-lg bg-brand-orange px-6 py-3.5 text-base font-semibold text-white shadow-lg shadow-brand-orange/20 hover:bg-brand-orangeHover transition-all focus:outline-none focus:ring-2 focus:ring-brand-orange/50 active:scale-[0.98]"
          >
            <span>Launch Live Playground</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href={PROJECT_METADATA.repoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-lg border border-surface-border bg-surface px-6 py-3.5 text-base font-medium text-slate-200 hover:bg-surface-hover hover:border-slate-600 transition-all focus:outline-none"
          >
            <Github className="h-5 w-5" />
            <span>View Source on GitHub</span>
          </Link>
        </div>

        {/* 30-Second Recruiter Pipeline Preview */}
        <div className="mt-8 max-w-4xl mx-auto">
          <div className="rounded-xl border border-surface-border bg-surface/90 p-4 sm:p-5 shadow-2xl backdrop-blur text-left">
            <div className="flex items-center justify-between pb-3 border-b border-surface-border mb-3 text-xs font-mono text-slate-400">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
                <span className="ml-2 text-slate-300 font-medium">runwise_lifecycle_pipeline.ts</span>
              </div>
              <span className="text-brand-orange font-semibold">Sub-Millisecond Routing & Deterministic Evals</span>
            </div>

            {/* Pipeline Stage Nodes */}
            <div className="grid grid-cols-2 md:grid-cols-6 gap-2 sm:gap-3 text-center">
              <div className="rounded-lg bg-charcoal p-3.5 border border-surface-border flex flex-col justify-between">
                <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">Input</span>
                <span className="text-sm font-semibold text-slate-200 mt-1">User Query</span>
                <span className="text-xs text-slate-400 mt-1 font-mono">Normalized</span>
              </div>

              <div className="rounded-lg bg-charcoal p-3.5 border border-brand-orange/40 flex flex-col justify-between shadow-[0_0_12px_rgba(249,115,22,0.15)]">
                <span className="text-xs font-mono text-brand-orange uppercase tracking-wider font-semibold">01 Classifier</span>
                <span className="text-sm font-semibold text-white mt-1">Risk Scoring</span>
                <span className="text-xs text-brand-orange font-mono font-medium">&lt; 0.1ms CPU</span>
              </div>

              <div className="rounded-lg bg-charcoal p-3.5 border border-surface-border flex flex-col justify-between">
                <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">02 Router</span>
                <span className="text-sm font-semibold text-slate-200 mt-1">Flash vs Pro</span>
                <span className="text-xs text-emerald-400 font-mono font-medium">-57.5% Cost</span>
              </div>

              <div className="rounded-lg bg-charcoal p-3.5 border border-surface-border flex flex-col justify-between">
                <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">03 Execution</span>
                <span className="text-sm font-semibold text-slate-200 mt-1">Agent Loop</span>
                <span className="text-xs text-slate-400 font-mono">LiteLLM / Vertex</span>
              </div>

              <div className="rounded-lg bg-charcoal p-3.5 border border-surface-border flex flex-col justify-between">
                <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">04 Sandbox</span>
                <span className="text-sm font-semibold text-slate-200 mt-1">Domain Tools</span>
                <span className="text-xs text-slate-400 font-mono">&lt; 2ms SQLite</span>
              </div>

              <div className="rounded-lg bg-charcoal p-3.5 border border-emerald-500/40 flex flex-col justify-between shadow-[0_0_12px_rgba(16,185,129,0.15)]">
                <span className="text-xs font-mono text-emerald-400 uppercase tracking-wider font-semibold">05 Reliability</span>
                <span className="text-sm font-semibold text-white mt-1">4-Tier Graders</span>
                <span className="text-xs text-emerald-400 font-mono font-medium">100% Deterministic</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
