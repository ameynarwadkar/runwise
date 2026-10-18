"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Github, Activity } from "lucide-react";
import { PROJECT_METADATA } from "@/lib/constants";

export function Navbar() {
  const [backendReady, setBackendReady] = useState<boolean | null>(null);

  useEffect(() => {
    // Check backend health silently
    fetch("/readyz")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        setBackendReady(data?.status === "ready");
      })
      .catch(() => {
        setBackendReady(false);
      });
  }, []);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-surface-border bg-charcoal/90 backdrop-blur-md transition-all">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface border border-surface-border group-hover:border-brand-orange/40 transition-colors">
              <span className="h-2.5 w-2.5 rounded-full bg-brand-orange shadow-[0_0_8px_#F97316]" />
            </div>
            <span className="text-lg font-bold tracking-tight text-white group-hover:text-brand-orange transition-colors">
              Runwise
            </span>
          </Link>

          {/* System Status Indicator */}
          <div className="hidden sm:flex items-center gap-2 ml-3 px-3 py-1 rounded-full bg-surface border border-surface-border text-xs font-mono font-medium text-slate-300">
            <span
              className={`h-2 w-2 rounded-full ${
                backendReady === true
                  ? "bg-emerald-400 shadow-[0_0_8px_#10B981]"
                  : "bg-amber-400 shadow-[0_0_8px_#F59E0B]"
              }`}
            />
            <span>
              {backendReady === true
                ? "Live Service Online"
                : "Demo Preview"}
            </span>
          </div>
        </div>

        {/* Desktop Nav Links */}
        <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-slate-300">
          <Link href="#overview" className="hover:text-white transition-colors">
            Overview
          </Link>
          <Link href="#architecture" className="hover:text-white transition-colors">
            Architecture
          </Link>
          <Link href="#benchmarks" className="hover:text-white transition-colors">
            Benchmarks
          </Link>
          <Link href="#contact" className="hover:text-white transition-colors">
            Contact
          </Link>
          <Link
            href={PROJECT_METADATA.repoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors"
          >
            <Github className="h-4 w-4" />
            <span>GitHub</span>
          </Link>
        </nav>

        {/* Action Button */}
        <div className="flex items-center gap-3">
          <Link
            href="/demo"
            className="inline-flex items-center gap-2 rounded-lg bg-brand-orange px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-orangeHover transition-all focus:outline-none focus:ring-2 focus:ring-brand-orange/50 active:scale-[0.98]"
          >
            <span>Try Live Demo</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </header>
  );
}
