import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.FASTAPI_URL || "http://127.0.0.1:8000";
  try {
    const res = await fetch(`${backendUrl}/readyz`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
    return NextResponse.json({ status: "offline" }, { status: 503 });
  } catch {
    return NextResponse.json({ status: "offline" }, { status: 503 });
  }
}
