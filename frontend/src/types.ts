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
  quality: QualityCheck | null;
}
