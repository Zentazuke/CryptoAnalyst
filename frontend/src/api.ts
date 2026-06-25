import type { ChartResponse, Commentary, MicroSnapshot } from "./types";

// Same-origin: the dev server proxies "/api" -> the analyst API (see
// vite.config.ts). This sidesteps browser CORS and IPv4/IPv6 loopback issues.
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function getJSON<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`API ${resp.status}: ${text || resp.statusText}`);
  }
  return resp.json();
}

export function fetchChart(symbol: string, timeframe: string, limit = 600): Promise<ChartResponse> {
  return getJSON<ChartResponse>(
    `/chart/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`,
  );
}

/** Latest microstructure snapshot, or null if none has been collected yet. */
export async function fetchMicro(symbol: string): Promise<MicroSnapshot | null> {
  try {
    const data = await getJSON<{ snapshots: MicroSnapshot[] }>(
      `/microstructure/${encodeURIComponent(symbol)}?limit=1`,
    );
    return data.snapshots[0] ?? null;
  } catch {
    return null; // 404 = not collected yet; treated as "unavailable"
  }
}

export async function fetchCommentary(symbol: string, timeframe: string): Promise<Commentary | null> {
  try {
    return await getJSON<Commentary>(
      `/commentary/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(timeframe)}`,
    );
  } catch {
    return null;
  }
}

export const API_BASE = BASE;
