import { NextRequest, NextResponse } from "next/server";
import { VERIFIED_REPLAYS } from "@/lib/replays";
import { PREDEFINED_SCENARIOS } from "@/lib/constants";

// Local in-memory rate limit fallback for development / local demo
const RATE_LIMIT_WINDOW_MS = 60 * 1000; // 1 minute
const MAX_REQUESTS_PER_WINDOW = 30;
const ipRequestCounts = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const current = ipRequestCounts.get(ip);

  if (!current || now > current.resetAt) {
    ipRequestCounts.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }

  if (current.count >= MAX_REQUESTS_PER_WINDOW) {
    return false;
  }

  current.count += 1;
  return true;
}

export async function POST(req: NextRequest) {
  const clientIp = req.headers.get("x-forwarded-for")?.split(",")[0].trim() || "127.0.0.1";

  if (!checkRateLimit(clientIp)) {
    return NextResponse.json(
      { detail: "Rate limit exceeded (30 requests/minute). Please slow down." },
      { status: 429 }
    );
  }

  try {
    const body = await req.json();
    const { scenario_id, auto_route = true } = body;

    if (!scenario_id || typeof scenario_id !== "string") {
      return NextResponse.json(
        { detail: "Missing or invalid 'scenario_id' parameter." },
        { status: 400 }
      );
    }

    const backendUrl = process.env.FASTAPI_URL || "http://127.0.0.1:8000";
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    // Forward service token or OIDC identity token if configured
    if (process.env.RUNWISE_SERVICE_TOKEN) {
      headers["X-Runwise-Service-Token"] = process.env.RUNWISE_SERVICE_TOKEN;
    }
    if (process.env.CLOUD_RUN_ID_TOKEN) {
      headers["Authorization"] = `Bearer ${process.env.CLOUD_RUN_ID_TOKEN}`;
    }

    // Call FastAPI backend with a 35-second abort controller
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 35000);

    try {
      const response = await fetch(`${backendUrl}/v1/demo/scenarios/run`, {
        method: "POST",
        headers,
        body: JSON.stringify({ scenario_id, auto_route }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        return NextResponse.json(data);
      }

      const errorText = await response.text();
      console.warn(`Upstream FastAPI returned ${response.status}: ${errorText}`);
    } catch (upstreamErr: unknown) {
      clearTimeout(timeoutId);
      console.warn("FastAPI backend unreachable, falling back to verified replay:", upstreamErr);
    }

    // Fallback: If backend is offline or unreachable, return genuine verified replay artifact
    const scenario = PREDEFINED_SCENARIOS.find((s) => s.id === scenario_id);
    if (scenario?.task_id && VERIFIED_REPLAYS[scenario.task_id]) {
      const replay = VERIFIED_REPLAYS[scenario.task_id];
      return NextResponse.json({
        ...replay,
        is_replay: true,
      });
    }

    return NextResponse.json(
      { detail: `Scenario '${scenario_id}' not found and backend is offline.` },
      { status: 503 }
    );
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Internal Server Error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
