import type { BehaviorCard, BehaviorsResponse, UnitsResponse, UnitDetail } from "./types";

export const CORPUS_CAPTION = "Share of analyzed wishlist conversations.";

export function apiBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  return raw.replace(/\/$/, "");
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${path}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchBehaviors(): Promise<BehaviorsResponse> {
  return getJson<BehaviorsResponse>("/behaviors");
}

export async function fetchBehavior(id: string): Promise<BehaviorCard> {
  return getJson<BehaviorCard>(`/behaviors/${encodeURIComponent(id)}`);
}

export async function fetchUnits(params: {
  q?: string;
  source?: string;
  stance?: string;
  barrier?: string;
  limit?: number;
  offset?: number;
}): Promise<UnitsResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.source) sp.set("source", params.source);
  if (params.stance) sp.set("stance", params.stance);
  if (params.barrier) sp.set("barrier", params.barrier);
  sp.set("limit", String(params.limit ?? 50));
  sp.set("offset", String(params.offset ?? 0));
  const qs = sp.toString();
  return getJson<UnitsResponse>(`/units?${qs}`);
}

export async function fetchUnit(id: number): Promise<UnitDetail> {
  return getJson<UnitDetail>(`/units/${id}`);
}

export function formatWhen(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function sourceLabel(source: string): string {
  const map: Record<string, string> = {
    reddit: "Reddit",
    youtube: "YouTube",
    app_store: "App Store",
    extract: "Extract",
    news: "News",
    linkedin: "LinkedIn",
    medium: "Medium",
    instagram: "Instagram",
    facebook: "Facebook",
    web_research: "Web research",
  };
  return map[source] || source;
}

export function bannerFromStatus(
  statuses: { source: string; status: string; message?: string | null }[],
): string | null {
  const bad = statuses.filter(
    (s) => s.source !== "extract" && s.status === "error",
  );
  if (!bad.length) return null;
  const parts = bad.map((s) => `${sourceLabel(s.source)} unreachable — showing stored insights`);
  return parts.join(" · ");
}
