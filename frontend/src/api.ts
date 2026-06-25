import type { ChartResponse, MicroSnapshot } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

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

export const API_BASE = BASE;
