import type { AlertJournalResponse, AlertsResponse, CarryRead, ChartResponse, Commentary, DataHealth, MicroSnapshot, OnChain, ScanResponse, Sentiment, VrpRead, VrpJournalResponse } from "./types";

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

export async function fetchCarry(symbol: string): Promise<CarryRead | null> {
  try {
    return await getJSON<CarryRead>(`/carry/${encodeURIComponent(symbol)}`);
  } catch {
    return null;
  }
}

export async function fetchVrpJournal(): Promise<VrpJournalResponse | null> {
  try {
    return await getJSON<VrpJournalResponse>(`/vrp-journal`);
  } catch {
    return null;
  }
}

export async function fetchDataHealth(): Promise<DataHealth | null> {
  try {
    return await getJSON<DataHealth>(`/data-health`);
  } catch {
    return null;
  }
}

// ---- P1.3 evidence panel (/explain) ---------------------------------------

export interface FiredSignal {
  signal: string;
  direction: "bullish" | "bearish";
  verdict: string;
  reliable: boolean;
  significant?: boolean;
  stable?: boolean;
  n?: number;
  accuracy?: number;
  base?: number;
  lift?: number;
  ci_low?: number;
  ci_high?: number;
  h1_acc?: number | null;
  h2_acc?: number | null;
  orientation?: string;
}

export interface ExplainResponse {
  symbol: string;
  timeframe: string;
  as_of: string;
  horizon: number;
  regime: {
    label: string;
    confidence: number;
    calibration?: { hit_rate?: number; base_rate?: number; lift?: number;
                    significant?: boolean; verdict?: string; count?: number } | null;
    calibration_horizon?: number;
  };
  fired: FiredSignal[];
  summary: {
    fired_total: number;
    reliable_bullish: number;
    reliable_bearish: number;
    read: string;
    note: string;
  };
}

export async function fetchExplain(symbol: string, timeframe: string): Promise<ExplainResponse | null> {
  try {
    return await getJSON<ExplainResponse>(
      `/explain/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(timeframe)}`,
    );
  } catch {
    return null;
  }
}

// ---- P3.2 metric explorer (/metric-history) --------------------------------

export interface MetricCatalogEntry {
  layer: string;
  symbol: string;
  metric: string;
  n: number;
  first_ts: number;
  last_ts: number;
}

export interface MetricSeriesPoint { ts: number; value: number }

export async function fetchMetricCatalog(symbol: string): Promise<MetricCatalogEntry[]> {
  try {
    const d = await getJSON<{ series: MetricCatalogEntry[] }>(
      `/metric-history/${encodeURIComponent(symbol)}`,
    );
    return d.series ?? [];
  } catch {
    return [];
  }
}

export async function fetchMetricSeries(
  layer: string, symbol: string, metric: string, limit = 2000,
): Promise<MetricSeriesPoint[]> {
  try {
    const d = await getJSON<{ series: MetricSeriesPoint[] }>(
      `/metric-history/${encodeURIComponent(symbol)}?layer=${encodeURIComponent(layer)}` +
      `&metric=${encodeURIComponent(metric)}&limit=${limit}`,
    );
    return d.series ?? [];
  } catch {
    return [];
  }
}

export const API_BASE = BASE;
