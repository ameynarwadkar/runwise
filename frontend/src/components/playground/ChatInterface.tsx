"use client";

import { useState, useRef, useEffect } from "react";
import {
  ArrowUp,
  Bot,
  User,
  CheckCircle2,
  XCircle,
  History,
  ChevronDown,
  ChevronUp,
  Loader2,
  Sparkles,
} from "lucide-react";
import { ChatMessage } from "@/lib/types";
import { ExecutionExplainer } from "./ExecutionExplainer";

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (prompt: string) => Promise<void>;
  isLoading: boolean;
  activeScenarioPrompt?: string;
  onClearActiveScenarioPrompt?: () => void;
}

export function ChatInterface({
  messages,
  onSendMessage,
  isLoading,
  activeScenarioPrompt,
  onClearActiveScenarioPrompt,
}: ChatInterfaceProps) {
  const [prompt, setPrompt] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (activeScenarioPrompt) {
      setPrompt(activeScenarioPrompt);
      if (onClearActiveScenarioPrompt) {
        onClearActiveScenarioPrompt();
      }
      // Focus textarea
      textareaRef.current?.focus();
    }
  }, [activeScenarioPrompt, onClearActiveScenarioPrompt]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isLoading) return;
    const currentPrompt = prompt;
    setPrompt("");
    await onSendMessage(currentPrompt);
  };

  return (
    <div className="flex flex-col flex-1 w-full max-w-3xl mx-auto">
      {/* Messages Stream */}
      <div className="flex-1 space-y-6 pb-6">
        {messages.length === 0 ? (
          <div className="py-16 sm:py-24 text-center">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-surface border border-surface-border text-brand-orange mb-4 shadow-sm">
              <Sparkles className="h-6 w-6" />
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              Runwise Live Playground
            </h2>
            <p className="mt-2 text-sm text-slate-300 max-w-md mx-auto leading-relaxed">
              Test production agent reliability with sub-millisecond model routing, deterministic evaluations, and sandboxed database actions.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id}>
              {msg.role === "user" ? (
                <UserMessageItem content={msg.content} />
              ) : (
                <AssistantMessageItem msg={msg} />
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex items-start gap-3.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-surface border border-surface-border text-brand-orange shadow-sm animate-pulse">
              <Bot className="h-4 w-4" />
            </div>
            <div className="rounded-2xl px-4 py-3 bg-surface border border-surface-border text-slate-300 text-xs font-mono flex items-center gap-2.5">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-orange" />
              <span>Routing model &amp; executing sandboxed agent loop...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ChatGPT-style Centered Input Container */}
      <div className="sticky bottom-4 w-full pt-2">
        <form
          onSubmit={handleSubmit}
          className="relative rounded-2xl border border-surface-border bg-charcoal/95 backdrop-blur-md shadow-2xl p-2 sm:p-2.5 focus-within:border-brand-orange/60 focus-within:ring-1 focus-within:ring-brand-orange/40 transition-all"
        >
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask Runwise anything or pick an example above..."
              rows={1}
              className="flex-1 bg-transparent px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none resize-none max-h-36 font-sans leading-relaxed"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
            />

            <button
              type="submit"
              disabled={!prompt.trim() || isLoading}
              className="h-9 w-9 rounded-xl bg-brand-orange text-white flex items-center justify-center hover:bg-brand-orangeHover transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-md shadow-brand-orange/20 shrink-0 active:scale-95"
              title="Send message"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowUp className="h-4 w-4 stroke-[2.5]" />
              )}
            </button>
          </div>
        </form>

        <p className="mt-2 text-center text-[11px] text-slate-400">
          Runwise verifies agent actions deterministically against sandboxed SQLite databases.
        </p>
      </div>
    </div>
  );
}

/**
 * User Message Bubble
 */
function UserMessageItem({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl bg-surface border border-surface-border px-4 py-3 text-sm text-slate-100 whitespace-pre-wrap leading-relaxed shadow-sm">
        {content}
      </div>
    </div>
  );
}

/**
 * Assistant Message with Simplified Chips & Collapsible "How Runwise handled this"
 */
function AssistantMessageItem({ msg }: { msg: ChatMessage }) {
  const [showExplainer, setShowExplainer] = useState(false);

  // Model Display Name (Gemini Flash vs Gemini Pro)
  const rawModel = msg.metadata?.model || msg.runData?.model || "";
  const isPro = rawModel.toLowerCase().includes("pro");
  const modelLabel = rawModel ? (isPro ? "Gemini Pro" : "Gemini Flash") : null;

  // Latency (e.g. 1.8s)
  const latencyMs = msg.metadata?.latency_ms ?? msg.runData?.latency_ms;
  const latencyLabel = latencyMs !== undefined ? `${(latencyMs / 1000).toFixed(1)}s` : null;

  // Evaluation status (ONLY when backed by actual grader results)
  const evalStatus =
    msg.metadata?.eval_verdict ||
    msg.runData?.evaluation?.overall_status ||
    null;
  const isEvaluated = evalStatus === "PASS" || evalStatus === "FAIL";

  const isReplay = msg.metadata?.is_replay || msg.runData?.is_replay;

  return (
    <div className="flex items-start gap-3.5">
      {/* Bot Icon */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-surface border border-surface-border text-brand-orange shadow-sm mt-0.5">
        <Bot className="h-4 w-4" />
      </div>

      <div className="flex-1 max-w-[92%]">
        {/* Assistant Response Bubble */}
        <div className="rounded-2xl bg-surface border border-surface-border px-4 py-3.5 text-sm text-slate-200 whitespace-pre-wrap leading-relaxed shadow-sm">
          {msg.content}
        </div>

        {/* Simplified Execution Feedback Strip */}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {/* Selected Model Chip */}
          {modelLabel && (
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-medium font-mono border ${
                isPro
                  ? "bg-purple-500/10 text-brand-purple border-purple-500/25"
                  : "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
              }`}
            >
              {modelLabel}
            </span>
          )}

          {/* Latency Chip */}
          {latencyLabel && (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono text-slate-300 bg-surface border border-surface-border">
              {latencyLabel}
            </span>
          )}

          {/* Evaluation Status Chip (only when backed by actual grader results!) */}
          {isEvaluated && (
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-medium border flex items-center gap-1 ${
                evalStatus === "PASS"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
                  : "bg-red-500/10 text-red-400 border-red-500/25"
              }`}
            >
              {evalStatus === "PASS" ? (
                <>
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Evaluated: Passed</span>
                </>
              ) : (
                <>
                  <XCircle className="h-3 w-3" />
                  <span>Evaluated: Failed</span>
                </>
              )}
            </span>
          )}

          {/* Recorded Demo Chip */}
          {isReplay && (
            <span
              className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/25 flex items-center gap-1 cursor-help"
              title="Previously captured, verified execution trace from the benchmark suite"
            >
              <History className="h-3 w-3" />
              <span>Recorded Demo</span>
            </span>
          )}

          {/* Collapsible Explainer Trigger: "How Runwise handled this" */}
          <button
            onClick={() => setShowExplainer((prev) => !prev)}
            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium text-slate-400 hover:text-white hover:bg-surface border border-transparent hover:border-surface-border transition-all ml-auto"
          >
            <span>How Runwise handled this</span>
            {showExplainer ? (
              <ChevronUp className="h-3 w-3 text-brand-orange" />
            ) : (
              <ChevronDown className="h-3 w-3 text-brand-orange" />
            )}
          </button>
        </div>

        {/* Collapsible Execution Explainer */}
        {showExplainer && (
          <ExecutionExplainer runData={msg.runData} />
        )}
      </div>
    </div>
  );
}
