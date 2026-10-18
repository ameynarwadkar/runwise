"use client";

import { useState, useEffect } from "react";
import { PlaygroundHeader } from "@/components/playground/PlaygroundHeader";
import { ScenarioSelector } from "@/components/playground/ScenarioSelector";
import { ChatInterface } from "@/components/playground/ChatInterface";
import { ExecutionInspector } from "@/components/playground/ExecutionInspector";
import { ChatMessage, AgentRunResponse, ScenarioDefinition } from "@/lib/types";
import { executeAgent, executeScenario, getReplay } from "@/lib/api";
import { PREDEFINED_SCENARIOS } from "@/lib/constants";
import { AlertCircle, History, Sparkles } from "lucide-react";

export default function DemoPage() {
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [runData, setRunData] = useState<AgentRunResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isReplay, setIsReplay] = useState(false);
  const [isOffline, setIsOffline] = useState(false);
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null);
  const [activeScenarioPrompt, setActiveScenarioPrompt] = useState<string>("");
  const [mobileTab, setMobileTab] = useState<"chat" | "inspector">("chat");

  // Initialize unique session on mount
  useEffect(() => {
    const freshSession = `sess_${Math.random().toString(36).substring(2, 10)}${Date.now().toString(36).substring(4)}`;
    setSessionId(freshSession);

    // Initial check for backend readiness
    fetch("/readyz")
      .then((res) => {
        if (!res.ok) setIsOffline(true);
      })
      .catch(() => setIsOffline(true));

    // Load initial scenario as visual demonstration
    const initialReplay = getReplay("task_inq_01");
    if (initialReplay) {
      setRunData(initialReplay);
      setMessages([
        {
          id: "initial_user",
          role: "user",
          content: "What items are in order ORD-101, and what is its current status?",
          timestamp: new Date().toLocaleTimeString(),
        },
        {
          id: "initial_assistant",
          role: "assistant",
          content: initialReplay.response,
          timestamp: new Date().toLocaleTimeString(),
          metadata: {
            model: initialReplay.model,
            tokens: initialReplay.tokens,
            latency_ms: initialReplay.latency_ms,
            cost_usd: initialReplay.cost_usd ?? undefined,
            is_replay: true,
            complexity_score: initialReplay.complexity_score,
          },
        },
      ]);
      setActiveScenarioId("scenario_order_lookup");
      setIsReplay(true);
    }
  }, []);

  // Reset Session
  const handleResetSession = () => {
    const freshSession = `sess_${Math.random().toString(36).substring(2, 10)}${Date.now().toString(36).substring(4)}`;
    setSessionId(freshSession);
    setMessages([]);
    setRunData(null);
    setActiveScenarioId(null);
    setActiveScenarioPrompt("");
    setIsReplay(false);
  };

  // Toggle Replay Mode
  const handleToggleReplayMode = () => {
    if (!isReplay) {
      const replay = getReplay("task_inq_01");
      if (replay) {
        setRunData(replay);
        setIsReplay(true);
      }
    } else {
      setIsReplay(false);
    }
  };

  // Select Scenario
  const handleSelectScenario = async (scenario: ScenarioDefinition) => {
    setActiveScenarioId(scenario.id);
    setActiveScenarioPrompt(scenario.prompt);

    if (isReplay || isOffline) {
      // In replay or offline mode, instantly load the verified replay artifact
      const replay = getReplay(scenario.task_id);
      if (replay) {
        setRunData(replay);
        setIsReplay(true);
        setMessages((prev) => [
          ...prev,
          {
            id: `usr_${Date.now()}`,
            role: "user",
            content: scenario.prompt,
            timestamp: new Date().toLocaleTimeString(),
          },
          {
            id: `ast_${Date.now()}`,
            role: "assistant",
            content: replay.response,
            timestamp: new Date().toLocaleTimeString(),
            metadata: {
              model: replay.model,
              tokens: replay.tokens,
              latency_ms: replay.latency_ms,
              cost_usd: replay.cost_usd ?? undefined,
              is_replay: true,
              complexity_score: replay.complexity_score,
            },
          },
        ]);
        return;
      }
    }

    // Live Execution via server-controlled endpoint
    setIsLoading(true);
    try {
      const userMsg: ChatMessage = {
        id: `usr_${Date.now()}`,
        role: "user",
        content: scenario.prompt,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      const result = await executeScenario(scenario.id, true);
      setRunData(result);
      if (result.is_replay) setIsReplay(true);

      const assistantMsg: ChatMessage = {
        id: `ast_${Date.now()}`,
        role: "assistant",
        content: result.response,
        timestamp: new Date().toLocaleTimeString(),
        metadata: {
          model: result.model,
          tokens: result.tokens,
          latency_ms: result.latency_ms,
          cost_usd: result.cost_usd ?? undefined,
          is_replay: result.is_replay,
          complexity_score: result.complexity_score,
        },
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed to execute scenario";
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          role: "assistant",
          content: `Backend Execution Error: ${errorMsg}. Switched to offline inspection mode.`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
      setIsOffline(true);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Freeform Chat Message
  const handleSendMessage = async (promptText: string, autoRoute: boolean) => {
    setIsLoading(true);
    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      role: "user",
      content: promptText,
      timestamp: new Date().toLocaleTimeString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const result = await executeAgent({
        prompt: promptText,
        session_id: sessionId,
        auto_route: autoRoute,
        mode: "conversation",
      });

      setRunData(result);
      if (result.is_replay) setIsReplay(true);

      const assistantMsg: ChatMessage = {
        id: `ast_${Date.now()}`,
        role: "assistant",
        content: result.response,
        timestamp: new Date().toLocaleTimeString(),
        metadata: {
          model: result.model,
          tokens: result.tokens,
          latency_ms: result.latency_ms,
          cost_usd: result.cost_usd ?? undefined,
          is_replay: result.is_replay,
          complexity_score: result.complexity_score,
        },
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Execution failed";
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          role: "assistant",
          content: `Execution Notice: ${errorMsg}. If live inference is offline, you can select any of the 5 pre-seeded scenarios above to inspect verified empirical traces.`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-charcoal text-slate-100 flex flex-col font-sans">
      <PlaygroundHeader
        sessionId={sessionId}
        isReplay={isReplay}
        onResetSession={handleResetSession}
        onToggleReplayMode={handleToggleReplayMode}
        isOffline={isOffline}
      />

      {/* Replay Notice Banner */}
      {isReplay && (
        <div className="bg-amber-500/10 border-b border-amber-500/30 px-4 py-2 text-xs text-amber-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 shrink-0" />
            <span>
              <strong>VERIFIED BENCHMARK REPLAY:</strong> Showing empirical trajectory recorded during the 50-task evaluation run. All token counts, tool calls, and grader outcomes are substantiated historical records.
            </span>
          </div>
          <button
            onClick={() => setIsReplay(false)}
            className="text-[11px] underline font-mono text-amber-200 hover:text-white"
          >
            Switch to Live Mode
          </button>
        </div>
      )}

      {/* Main Two-Column Layout */}
      <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
        {/* Scenario Quick Selector */}
        <ScenarioSelector
          activeScenarioId={activeScenarioId}
          onSelectScenario={handleSelectScenario}
          disabled={isLoading}
        />

        {/* Mobile Tab Switcher */}
        <div className="flex lg:hidden mb-4 p-1 rounded-lg bg-surface border border-surface-border text-xs font-mono">
          <button
            onClick={() => setMobileTab("chat")}
            className={`flex-1 py-2 rounded-md font-semibold ${
              mobileTab === "chat" ? "bg-brand-orange text-white" : "text-slate-400"
            }`}
          >
            Chat &amp; Execution
          </button>
          <button
            onClick={() => setMobileTab("inspector")}
            className={`flex-1 py-2 rounded-md font-semibold ${
              mobileTab === "inspector" ? "bg-brand-orange text-white" : "text-slate-400"
            }`}
          >
            Execution Inspector
          </button>
        </div>

        {/* Dual Split Panels */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column (55%): Chat Interface */}
          <div className={`lg:col-span-7 ${mobileTab === "chat" ? "block" : "hidden lg:block"}`}>
            <ChatInterface
              messages={messages}
              onSendMessage={handleSendMessage}
              isLoading={isLoading}
              activeScenarioPrompt={activeScenarioPrompt}
              onClearActiveScenarioPrompt={() => setActiveScenarioPrompt("")}
            />
          </div>

          {/* Right Column (45%): Execution Inspector */}
          <div className={`lg:col-span-5 ${mobileTab === "inspector" ? "block" : "hidden lg:block"}`}>
            <ExecutionInspector runData={runData} />
          </div>
        </div>
      </main>
    </div>
  );
}
