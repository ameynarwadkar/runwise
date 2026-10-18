import { AgentRunRequest, AgentRunResponse, ScenarioDefinition } from "./types";
import { PREDEFINED_SCENARIOS } from "./constants";
import { VERIFIED_REPLAYS } from "./replays";

/**
 * Executes a customer support turn or pre-seeded scenario.
 * Tries live Next.js BFF proxy first. If the backend is offline, exhausted,
 * or unreachable, falls back gracefully to sanitized verified benchmark replays.
 */
export async function executeAgent(request: AgentRunRequest): Promise<AgentRunResponse> {
  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Network error" }));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    return await res.json();
  } catch (error) {
    // If backend is offline and a matching task_id exists in our replay library, serve replay with notice
    if (request.task_id && VERIFIED_REPLAYS[request.task_id]) {
      const replay = VERIFIED_REPLAYS[request.task_id];
      return {
        ...replay,
        session_id: request.session_id || replay.session_id,
        is_replay: true,
      };
    }
    throw error;
  }
}

/**
 * Executes a server-controlled scenario by ID.
 */
export async function executeScenario(
  scenarioId: string,
  autoRoute: boolean = true
): Promise<AgentRunResponse> {
  const scenario = PREDEFINED_SCENARIOS.find((s) => s.id === scenarioId);

  try {
    const res = await fetch("/api/scenarios/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario_id: scenarioId, auto_route: autoRoute }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Network error" }));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    return await res.json();
  } catch (error) {
    // If backend is offline, gracefully return the verified replay for this scenario
    if (scenario?.task_id && VERIFIED_REPLAYS[scenario.task_id]) {
      return {
        ...VERIFIED_REPLAYS[scenario.task_id],
        is_replay: true,
      };
    }
    throw error;
  }
}

/**
 * Returns a static verified benchmark replay.
 */
export function getReplay(taskId: string): AgentRunResponse | null {
  return VERIFIED_REPLAYS[taskId] || null;
}
