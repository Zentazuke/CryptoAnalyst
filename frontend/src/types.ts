export interface LinePoint {
  time: number;
  value: number;
}

export interface FeedHealth {
  symbol: string;
  timeframe: string;
  last_candle: string | null;
  age_seconds: number | null;
  stale: boolean;
}

export interface SchedulerTask {
  name: string;
  interval_s: number;
  runs: number;
  errors: number;
  last_run: number;
}

export interface DataHealth {
  status: "ok" | "degraded" | "stale";
  now: string;
  feeds: FeedHealth[];
  scheduler: { enabled: boolean; running: boolean; errors: number; tasks: SchedulerTask[] };
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface QualityCheck {
  check_name: string;
  status: string;
  detail: string;
  created_ts: number;
}

export interface RegimePoint {
  time: number;
  label: string;
  confidence: number;
}

export interface Calibration {
  count: number;
  hit_rate: number | null;
  base_rate: number | null;
  lift: number | null;
  ci_low?: number | null;
  ci_high?: number | null;
  significant?: boolean;
  verdict?: "edge" | "negative" | "no-edge" | "insufficient" | "no-data";
}

export interface RegimeCurrent {
  ts: number | null;
  label: string;
  confidence: number;
  features: Record<string, number | null>;
  reasons: string[];
  calibration: Calibration | null;
  calibration_horizon: number;
}

export interface Level {
  price: number;
  types: string[];
  touches: number;
  dist_pct: number;
  dist_atr: number;
}

export interface Levels {
  price: number | null;
  atr?: number;
  support: Level[];
  resistance: Level[];
  nearest_support: Level | null;
  nearest_resistance: Level | null;
  levels: Level[];
}

export interface ChartResponse {
  symbol: string;
  timeframe: string;
  indicator_version: string;
  source: string;
  last_candle: string;
  bars: number;
  candles: Candle[];
  volume: LinePoint[];
  overlays: Record<string, LinePoint[]>;
  panels: Record<string, LinePoint[]>;
  regime: RegimePoint[];
  regime_current: RegimeCurrent;
  levels: Levels;
  quality: QualityCheck | null;
}

export interface RiskFrame {
  price: number;
  horizon: number;
  expected_move_pct: number;
  band_low: number;
  band_high: number;
  atr: number;
  atr_pct: number;
  vol_regime: string;
  bandwidth_pct: number | null;
  long: { stop: number; target: number | null; rr: number | null };
  short: { stop: number; target: number | null; rr: number | null };
  implied_vol?: { dvol: number; realized_vol_annual: number; premium_pts: number; signal: string } | null;
}

export interface MetricRead {
  key: string;
  title: string;
  bias: string | null;
  reading: string;
  meaning: string;
  outlook: string;
}

export interface EnsembleSignal {
  weight: number;
  call: number;
  contribution: number;
  train_acc: number | null;
  train_n: number;
}

export interface Evidence {
  n: number;
  hit_rate: number | null;
  ci_low: number | null;
  ci_high: number | null;
  base_rate: number | null;
  lift: number | null;
  lift_ci_low: number | null;
  lift_ci_high: number | null;
  p_value: number | null;
  significant: boolean;
  verdict: "edge" | "negative" | "no-edge" | "insufficient" | "no-data";
}

export interface EnsembleRead {
  horizon: number;
  lean: string;
  score: number;
  normalized: number;
  signals: Record<string, EnsembleSignal>;
  calibration: Evidence | null;
}

export interface Commentary {
  symbol: string;
  timeframe: string;
  as_of: string;
  metric_reads?: MetricRead[];
  ensemble?: EnsembleRead | null;
  headline: string;
  whats_happening: string[];
  what_it_means: string[];
  outlook: {
    bias: string;
    confidence: string;
    horizon_bars: number;
    text: string;
    invalidation: string | null;
  };
  risk: RiskFrame | null;
  caveat: string;
}

export interface ScanRow {
  rank: number;
  symbol: string;
  instrument: string;
  price: number;
  regime: string;
  confidence: number;
  rsi: number | null;
  adx: number | null;
  above_ema: boolean;
  momentum: number;
  funding: number | null;
  rs_vs_btc: number | null;
}

export interface ScanResponse {
  timeframe: string;
  lookback: number;
  count: number;
  rows: ScanRow[];
  aggregates: {
    regime_counts: Record<string, number>;
    pct_uptrend: number;
    pct_downtrend: number;
    pct_above_ema20: number;
    avg_funding: number | null;
    breadth: string;
    rotation: string | null;
    pct_outperform_btc: number | null;
  };
  setups: { symbol: string; kind: string; note: string }[];
  cached?: boolean;
}

export interface Alert {
  symbol: string;
  kind: string;
  direction: string;
  severity: number;
  signals: string[];
  note: string;
  track_record?: { count: number; hit_rate: number; base_rate: number; lift: number | null } | null;
}

export interface AlertsResponse {
  timeframe: string;
  breadth: string;
  alerts: Alert[];
}

export interface AlertJournalEntry {
  fired_ts: number;
  fired_at: string;
  symbol: string;
  kind: string;
  direction: string;
  severity: number;
  timeframe: string;
  price_at_fire: number;
  since_ret: number | null;
  on_track: boolean | null;
}

export interface AlertJournalResponse {
  count: number;
  on_track_rate: number | null;
  alerts: AlertJournalEntry[];
}

export interface Sentiment {
  symbol: string;
  available: boolean;
  outlook?: {
    outlook_score?: number;
    label?: string;
    confidence?: number;
    context_tilt?: number;
    direction_prob_6h?: number | null;
    horizons?: { horizon_seconds?: number; label?: string; score?: number; confidence?: number }[];
  };
  context?: {
    fear_greed_value?: number;
    fear_greed_label?: string;
    btc_dominance_pct?: number;
    market_cap_change_24h_pct?: number;
  } | null;
  snapshot?: {
    average_sentiment?: number;
    sentiment_velocity?: number;
    attention_spike?: number;
    data_quality?: number;
    message_count?: number;
    price_change_pct?: number;
  } | null;
  positioning?: {
    global_account_ratio?: number;
    top_account_ratio?: number;
    top_position_ratio?: number;
    taker_ratio?: number;
    signal?: string | number;
  } | null;
  derivatives?: {
    funding_rate?: number;
    open_interest_usd?: number;
    funding_signal?: string;
  } | null;
  insights?: {
    event_count?: number;
    terms?: { term?: string; count?: number }[];
    sources?: Record<string, { count?: number; avg_sentiment?: number }>;
  } | null;
  direction_prob_6h?: number | null;
  alerts?: Record<string, unknown> | null;
  recent?: { events?: { text?: string; score?: number; source?: string }[] } | null;
}

export interface OnChain {
  symbol: string;
  available: boolean;
  asset?: string;
  active_addresses?: number;
  addr_trend_30d?: number | null;
  addr_percentile_90d?: number | null;
  tx_count?: number | null;
  tx_trend_30d?: number | null;
  price_trend_30d?: number | null;
  divergence?: string;
  divergence_calibration?: Evidence | null;
}

export interface MicroSnapshot {
  symbol: string;
  ts: number;
  snapshot_time: string;
  mid: number;
  best_bid: number;
  best_ask: number;
  spread_bps: number;
  depth_band_bps: number;
  bid_depth_quote: number;
  ask_depth_quote: number;
  open_interest: number | null;
  funding_rate: number | null;
  mark_price: number | null;
  index_price: number | null;
  basis_bps: number | null;
  live?: boolean;
}
