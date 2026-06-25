export interface LinePoint {
  time: number;
  value: number;
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
  quality: QualityCheck | null;
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
}
