import type { AlertJournalResponse, AlertsResponse, ChartResponse, Commentary, DataHealth, MicroSnapshot, OnChain, ScanResponse, Sentiment, VrpRead } from "./types";

// Same-origin: the dev server proxies "/api" -> the analyst API (see
// vite.config.ts). This sidesteps browser CORS and IPv4/IPv6 loopback issues.
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Retry transient failures (network errors + 5xx) — the analyst API can take a
// few seconds to finish booting (pandas/TA-Lib/sklearn + model), so an early
// request shouldn't surface as a hard error.
async function getJSON<T>(path: string, attempts = 4): Promise<T> {
  let lastErr: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      const resp = await fetch(`${BASE}${path}`);
      if (resp.ok) return resp.json();
      if (resp.status >= 500 && i < attempts - 1) {
        await sleep(800);
        continue;
      }
      const text = await resp.text().catch(() => "");
      throw new Error(`API ${resp.status}: ${text || resp.statusText}`);
    } catch (e) {
      lastErr = e;
      if (i < attempts - 1) {
        await sleep(800);
        continue;
      }
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error("request failed");
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

export async function fetchSentiment(symbol: string): Promise<Sentiment | null> {
  try {
    return await getJSON<Sentiment>(`/sentiment/${encodeURIComponent(symbol)}`);
  } catch {
    return null;
  }
}

export async function fetchScan(timeframe = "4h", limit = 24): Promise<ScanResponse | null> {
  try {
    return await getJSON<ScanResponse>(`/scan?timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`);
  } catch {
    return null;
  }
}

export async function fetchAlerts(timeframe = "4h", limit = 24): Promise<AlertsResponse | null> {
  try {
    return await getJSON<AlertsResponse>(`/alerts?timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`);
  } catch {
    return null;
  }
}

export async function fetchAlertJournal(limit = 40): Promise<AlertJournalResponse | null> {
  try {
    return await getJSON<AlertJournalResponse>(`/alert-journal?limit=${limit}`);
  } catch {
    return null;
  }
}

export async function fetchOnchain(symbol: string): Promise<OnChain | null> {
  try {
    return await getJSON<OnChain>(`/onchain/${encodeURIComponent(symbol)}`);
  } catch {
    return null;
  }
}

export async function fetchVrp(symbol: string): Promise<VrpRead | null> {
  try {
    return await getJSON<VrpRead>(`/vrp/${encodeURIComponent(symbol)}`);
  } catch {
    return null; // 404 = no DVOL coverage (non BTC/ETH)
  }
}

export async function fetchDataHealth(): Promise<DataHealth | null> {
  try {
    return await getJSON<DataHealth>(`/data-health`);
  } catch {
    return null;
  }
}

export const API_BASE = BASE;
