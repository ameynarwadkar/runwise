"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Zap, Bot, User, AlertTriangle, ShieldCheck, Loader2 } from "lucide-react";
import { ChatMessage } from "@/lib/types";

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (prompt: string, autoRoute: boolean) => Promise<void>;
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
  const [autoRoute, setAutoRoute] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeScenarioPrompt) {
      setPrompt(activeScenarioPrompt);
      if (onClearActiveScenarioPrompt) {
        onClearActiveScenarioPrompt();
      }
    }
  }, [activeScenarioPrompt, onClearActiveScenarioPrompt]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isLoading) return;
    const currentPrompt = prompt;
    setPrompt("");
    await onSendMessage(currentPrompt, autoRoute);
  };

  return (
    <div className="flex flex-col h-[650px] rounded-xl border border-surface-border bg-charcoal overflow-hidden shadow-xl">
      {/* Demo Credentials Notice Banner */}
      <div className="bg-surface/90 border-b border-surface-border px-4 py-2 text-[11px] text-slate-400 flex items-center gap-2">
        <ShieldCheck className="h-3.5 w-3.5 text-brand-orange shrink-0" />
        <span>
          <strong className="text-slate-300">Sandbox Notice:</strong> Verification codes (e.g. 1234) are demo tokens testing authorization-before-action policy. Not production auth.
        </span>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
            <Bot className="h-10 w-10 text-slate-600 mb-3" />
            <p className="text-sm font-medium text-slate-300">
              Select a scenario above or type a customer inquiry.
            </p>
            <p className="text-xs text-slate-400 mt-1 max-w-sm">
              The AutoRouter will dynamically inspect request complexity and select between Gemini 2.5 Flash and Pro.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 text-xs leading-relaxed ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {msg.role === "assistant" && (
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface border border-surface-border text-brand-orange">
                  <Bot className="h-4 w-4" />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-xl p-3.5 ${
                  msg.role === "user"
                    ? "bg-brand-orange text-white"
                    : "bg-surface border border-surface-border text-slate-200"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>

                {/* Metadata Strip for Assistant Messages */}
                {msg.role === "assistant" && msg.metadata && (
                  <div className="mt-2.5 pt-2 border-t border-surface-border/60 flex flex-wrap items-center gap-2 text-[10px] font-mono text-slate-400">
                    {msg.metadata.model && (
                      <span className="text-brand-orange">
                        {msg.metadata.model.replace("vertex_ai/", "")}
                      </span>
                    )}
                    {msg.metadata.latency_ms && (
                      <span>{(msg.metadata.latency_ms / 1000).toFixed(2)}s</span>
                    )}
                    {msg.metadata.tokens && (
                      <span>{msg.metadata.tokens.total_tokens} tokens</span>
                    )}
                    {msg.metadata.cost_usd !== undefined && msg.metadata.cost_usd !== null && (
                      <span className="text-emerald-400">
                        ${msg.metadata.cost_usd < 0.0001 ? "<$0.0001" : msg.metadata.cost_usd.toFixed(4)}
                      </span>
                    )}
                    {msg.metadata.is_replay && (
                      <span className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        REPLAY
                      </span>
                    )}
                  </div>
                )}
              </div>

              {msg.role === "user" && (
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface border border-surface-border text-slate-300">
                  <User className="h-4 w-4" />
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex gap-3 text-xs leading-relaxed justify-start">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface border border-surface-border text-brand-orange animate-pulse">
              <Bot className="h-4 w-4" />
            </div>
            <div className="rounded-xl p-3.5 bg-surface border border-surface-border text-slate-400 flex items-center gap-2 font-mono">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-orange" />
              <span>Executing AutoRouter &amp; Agent Loop...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar Form */}
      <form onSubmit={handleSubmit} className="p-3 sm:p-4 border-t border-surface-border bg-charcoal-subtle">
        <div className="flex items-center justify-between mb-2 text-[11px] text-slate-400 font-mono">
          <label className="flex items-center gap-1.5 cursor-pointer hover:text-slate-200 transition-colors">
            <input
              type="checkbox"
              checked={autoRoute}
              onChange={(e) => setAutoRoute(e.target.checked)}
              className="rounded border-slate-700 bg-surface text-brand-orange focus:ring-0 focus:ring-offset-0"
            />
            <span>Auto-Routing (Flash vs Pro)</span>
          </label>
          <span>{prompt.length}/1000 chars</span>
        </div>

        <div className="flex gap-2">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value.slice(0, 1000))}
            placeholder="Type customer query or load a scenario above..."
            rows={2}
            className="flex-1 rounded-lg bg-surface border border-surface-border px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-orange/60 resize-none font-sans"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
          />
          <button
            type="submit"
            disabled={!prompt.trim() || isLoading}
            className="self-end px-4 py-2.5 rounded-lg bg-brand-orange text-white text-xs font-semibold hover:bg-brand-orangeHover transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 shadow-sm active:scale-95"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <span>Run</span>
                <Send className="h-3.5 w-3.5" />
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
