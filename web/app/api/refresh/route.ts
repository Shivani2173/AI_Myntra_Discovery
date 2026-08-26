import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function apiBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function POST() {
  const token = process.env.INGEST_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: "INGEST_TOKEN is not set in web/.env.local" },
      { status: 500 },
    );
  }
  try {
    const res = await fetch(`${apiBase()}/jobs/gather`, {
      method: "POST",
      headers: {
        "X-Ingest-Token": token,
        Accept: "application/json",
      },
      cache: "no-store",
    });
    const text = await res.text();
    let body: unknown = text;
    try {
      body = JSON.parse(text);
    } catch {
      /* keep text */
    }
    if (!res.ok) {
      return NextResponse.json(
        { error: "Gather start failed", detail: body },
        { status: res.status },
      );
    }
    return NextResponse.json(body);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to reach API" },
      { status: 502 },
    );
  }
}
