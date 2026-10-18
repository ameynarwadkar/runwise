import Link from "next/link";
import { PROJECT_METADATA } from "@/lib/constants";
import { Github, ExternalLink } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-surface-border bg-charcoal-darker py-10 text-xs text-slate-400">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="h-2 w-2 rounded-full bg-brand-orange" />
            <span className="font-bold text-white tracking-tight text-sm">Runwise</span>
            <span className="text-slate-600">|</span>
            <span>Production AI Agent Reliability Infrastructure</span>
          </div>

          <div className="flex items-center gap-6">
            <Link
              href="/demo"
              className="text-slate-300 hover:text-white transition-colors"
            >
              Playground
            </Link>
            <Link
              href={PROJECT_METADATA.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-300 hover:text-white transition-colors flex items-center gap-1"
            >
              <span>GitHub</span>
              <ExternalLink className="h-3 w-3" />
            </Link>
            <span className="text-slate-500 font-mono">
              License: {PROJECT_METADATA.license}
            </span>
          </div>
        </div>

        <div className="mt-6 pt-6 border-t border-surface-border/50 text-center text-slate-500 font-mono text-[11px]">
          Engineered with rigor by {PROJECT_METADATA.authorName}. Built on FastAPI, Google Vertex AI, OpenTelemetry, and Next.js 15.
        </div>
      </div>
    </footer>
  );
}
