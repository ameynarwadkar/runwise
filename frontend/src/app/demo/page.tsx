"use client";

import { useState, useEffect } from "react";
import { PlaygroundHeader } from "@/components/playground/PlaygroundHeader";
import { ScenarioSelector } from "@/components/playground/ScenarioSelector";
import { ChatInterface } from "@/components/playground/ChatInterface";
import { ChatMessage, AgentRunResponse, ScenarioDefinition } from "@/lib/types";
import { executeAgent, executeScenario, getReplay } from "@/lib/api";

export default function DemoPage() {
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isReplay, setIsReplay] = useState(false);
  const [manualReplayMode, setManualReplayMode] = useState(false);
  const [isOffline, setIsOffline] = useState(false);
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null);
  const [activeScenarioPrompt, setActiveScenarioPrompt] = useState<string>("");

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
          runData: initialReplay,
          metadata: {
            model: initialReplay.model,
            tokens: initialReplay.tokens,
            latency_ms: initialReplay.latency_ms,
            cost_usd: initialReplay.cost_usd ?? undefined,
            is_replay: true,
            complexity_score: initialReplay.complexity_score,
            eval_verdict: initialReplay.evaluation?.overall_status,
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
    setActiveScenarioId(null);
    setActiveScenarioPrompt("");
    setIsReplay(false);
    setManualReplayMode(false);
  };

  // Select Scenario
  const handleSelectScenario = async (scenario: ScenarioDefinition) => {
    setActiveScenarioId(scenario.id);
    setActiveScenarioPrompt(scenario.prompt);

    if (manualReplayMode || isOffline) {
      // In replay or offline mode, load the verified replay artifact
      const replay = getReplay(scenario.task_id);
      if (replay) {
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
            runData: replay,
            metadata: {
              model: replay.model,
              tokens: replay.tokens,
              latency_ms: replay.latency_ms,
              cost_usd: replay.cost_usd ?? undefined,
              is_replay: true,
              complexity_score: replay.complexity_score,
              eval_verdict: replay.evaluation?.overall_status,
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
      setIsReplay(Boolean(result.is_replay));

      const assistantMsg: ChatMessage = {
        id: `ast_${Date.now()}`,
        role: "assistant",
        content: result.response,
        timestamp: new Date().toLocaleTimeString(),
        runData: result,
        metadata: {
          model: result.model,
          tokens: result.tokens,
          latency_ms: result.latency_ms,
          cost_usd: result.cost_usd ?? undefined,
          is_replay: result.is_replay,
          complexity_score: result.complexity_score,
          eval_verdict: result.evaluation?.overall_status,
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
          content: `Backend Execution Notice: ${errorMsg}. Switched to recorded demo inspection.`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
      setIsOffline(true);
    } finally {
      setIsLoading(false);
    }
  };

  // Custom User Prompt
  const handleSendMessage = async (promptText: string) => {
    setActiveScenarioId(null);
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
        auto_route: true,
        mode: "conversation",
      });

      if (result.is_replay) setIsReplay(true);

      const assistantMsg: ChatMessage = {
        id: `ast_${Date.now()}`,
        role: "assistant",
        content: result.response,
        timestamp: new Date().toLocaleTimeString(),
        runData: result,
        metadata: {
          model: result.model,
          tokens: result.tokens,
          latency_ms: result.latency_ms,
          cost_usd: result.cost_usd ?? undefined,
          is_replay: result.is_replay,
          complexity_score: result.complexity_score,
          eval_verdict: result.evaluation?.overall_status,
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
          content: `Notice: ${errorMsg}. Pick an example above to inspect a verified execution trace.`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-charcoal text-slate-100 flex flex-col font-sans selection:bg-brand-orange selection:text-white">
      <PlaygroundHeader
        isReplay={isReplay}
        onResetSession={handleResetSession}
        onSwitchToLive={() => {
          setIsReplay(false);
          setManualReplayMode(false);
        }}
        isOffline={isOffline}
      />

      {/* Centered Conversation-First Main Container */}
      <main className="flex-1 max-w-3xl mx-auto w-full px-4 py-6 sm:py-8 flex flex-col">
        {/* Compact Clickable Examples */}
        <ScenarioSelector
          activeScenarioId={activeScenarioId}
          onSelectScenario={handleSelectScenario}
          disabled={isLoading}
        />

        {/* Primary Chat Interface */}
        <ChatInterface
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          activeScenarioPrompt={activeScenarioPrompt}
          onClearActiveScenarioPrompt={() => setActiveScenarioPrompt("")}
        />
      </main>
    </div>
  );
}
