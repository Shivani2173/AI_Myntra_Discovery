import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function apiBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const token = process.env.INGEST_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: "INGEST_TOKEN is not set in web/.env.local" },
      { status: 500 },
    );
  }
  try {
    const res = await fetch(`${apiBase()}/jobs/${encodeURIComponent(id)}`, {
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
      /* keep */
    }
    if (!res.ok) {
      return NextResponse.json(
        { error: "Job poll failed", detail: body },
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
