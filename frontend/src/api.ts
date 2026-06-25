import type { ChartResponse } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function fetchChart(
  symbol: string,
  timeframe: string,
  limit = 500,
): Promise<ChartResponse> {
  const url = `${BASE}/chart/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(
    timeframe,
  )}&limit=${limit}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`API ${resp.status}: ${text || resp.statusText}`);
  }
  return resp.json();
}

export const API_BASE = BASE;
