import Link from "next/link";
import { Linkedin, Github, Mail, ArrowUpRight } from "lucide-react";
import { PROJECT_METADATA } from "@/lib/constants";

export function ContactSection() {
  return (
    <section id="contact" className="py-20 bg-charcoal border-t border-surface-border">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-surface-border bg-surface p-8 sm:p-12 text-center max-w-4xl mx-auto shadow-2xl relative overflow-hidden">
          {/* Subtle background glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-48 bg-brand-orange/10 blur-[90px] rounded-full pointer-events-none" />

          <span className="text-xs font-mono uppercase tracking-widest text-brand-orange">
            Engineering Connect
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mt-2">
            Interested in how Runwise works?
          </h2>
          <p className="mt-4 text-base text-slate-300 max-w-2xl mx-auto leading-relaxed">
            Open to AI engineering opportunities, technical collaborations, and conversations about production AI systems, LLMOps, and agent evaluation.
          </p>

          {/* Contact Direct Cards */}
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4 text-left max-w-2xl mx-auto">
            <Link
              href={PROJECT_METADATA.linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-4 rounded-xl bg-charcoal border border-surface-border hover:border-brand-orange/50 hover:bg-surface-hover transition-all flex items-center justify-between group"
            >
              <div className="flex items-center gap-3">
                <Linkedin className="h-5 w-5 text-slate-400 group-hover:text-brand-orange transition-colors" />
                <div>
                  <div className="text-sm font-semibold text-white">LinkedIn</div>
                  <div className="text-xs text-slate-400 font-mono">ameynarwadkar</div>
                </div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-slate-500 group-hover:text-white transition-colors" />
            </Link>

            <Link
              href={PROJECT_METADATA.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-4 rounded-xl bg-charcoal border border-surface-border hover:border-brand-orange/50 hover:bg-surface-hover transition-all flex items-center justify-between group"
            >
              <div className="flex items-center gap-3">
                <Github className="h-5 w-5 text-slate-400 group-hover:text-brand-orange transition-colors" />
                <div>
                  <div className="text-sm font-semibold text-white">GitHub</div>
                  <div className="text-xs text-slate-400 font-mono">runwise repo</div>
                </div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-slate-500 group-hover:text-white transition-colors" />
            </Link>

            <Link
              href={`mailto:${PROJECT_METADATA.email}`}
              className="p-4 rounded-xl bg-charcoal border border-surface-border hover:border-brand-orange/50 hover:bg-surface-hover transition-all flex items-center justify-between group"
            >
              <div className="flex items-center gap-3">
                <Mail className="h-5 w-5 text-slate-400 group-hover:text-brand-orange transition-colors" />
                <div>
                  <div className="text-sm font-semibold text-white">Email</div>
                  <div className="text-xs text-slate-400 font-mono">{PROJECT_METADATA.email}</div>
                </div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-slate-500 group-hover:text-white transition-colors" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
