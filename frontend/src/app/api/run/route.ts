import { NextRequest, NextResponse } from "next/server";

// Local in-memory rate limit fallback for development / local demo
const RATE_LIMIT_WINDOW_MS = 60 * 1000; // 1 minute
const MAX_REQUESTS_PER_WINDOW = 30;
const MAX_PROMPT_LENGTH = 1000;
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
    const { prompt, session_id, customer_id, auto_route = true, task_id } = body;

    if (!prompt || typeof prompt !== "string") {
      return NextResponse.json(
        { detail: "Missing or invalid 'prompt' parameter." },
        { status: 400 }
      );
    }

    if (prompt.length > MAX_PROMPT_LENGTH) {
      return NextResponse.json(
        { detail: `Prompt length exceeds maximum allowed limit of ${MAX_PROMPT_LENGTH} characters.` },
        { status: 400 }
      );
    }

    if (!session_id || typeof session_id !== "string") {
      return NextResponse.json(
        { detail: "Missing or invalid 'session_id' parameter." },
        { status: 400 }
      );
    }

    const backendUrl = process.env.FASTAPI_URL || "http://127.0.0.1:8000";
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (process.env.RUNWISE_SERVICE_TOKEN) {
      headers["X-Runwise-Service-Token"] = process.env.RUNWISE_SERVICE_TOKEN;
    }
    if (process.env.CLOUD_RUN_ID_TOKEN) {
      headers["Authorization"] = `Bearer ${process.env.CLOUD_RUN_ID_TOKEN}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 20000);

    try {
      const response = await fetch(`${backendUrl}/v1/agent/run`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          prompt,
          session_id,
          customer_id: customer_id || null,
          auto_route,
          task_id: task_id || null,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        return NextResponse.json(data);
      }

      const errorData = await response.json().catch(() => ({ detail: "Upstream error" }));
      return NextResponse.json(
        { detail: errorData.detail || `FastAPI backend error (${response.status})` },
        { status: response.status }
      );
    } catch (upstreamErr: unknown) {
      clearTimeout(timeoutId);
      return NextResponse.json(
        {
          detail:
            "Live FastAPI agent service is currently offline. To test free-form queries against the live agent, start the FastAPI service (`uv run uvicorn runwise.service.app:app --port 8000`). Alternatively, select any pre-seeded Scenario to explore deterministic grading and execution traces.",
        },
        { status: 503 }
      );
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Internal Server Error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
