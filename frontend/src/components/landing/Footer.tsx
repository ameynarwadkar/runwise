import Link from "next/link";
import { PROJECT_METADATA } from "@/lib/constants";
import { Github, ExternalLink } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-surface-border bg-charcoal-darker py-8 text-xs text-slate-400">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <span className="h-2 w-2 rounded-full bg-brand-orange" />
            <span className="font-bold text-white tracking-tight text-sm">Runwise</span>
            <span className="text-slate-600">•</span>
            <span className="text-slate-400">Apache 2.0 License</span>
          </div>

          <div className="flex items-center gap-6 text-sm font-medium">
            <Link
              href={PROJECT_METADATA.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-300 hover:text-white transition-colors flex items-center gap-1.5"
            >
              <Github className="h-4 w-4" />
              <span>GitHub</span>
            </Link>
            <Link
              href="/demo"
              className="text-brand-orange hover:text-brand-orangeHover transition-colors"
            >
              Live Demo
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
