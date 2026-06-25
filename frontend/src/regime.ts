export const REGIME_COLORS: Record<string, string> = {
  range: "#3fb950",
  trend_up: "#58a6ff",
  trend_down: "#f0883e",
  breakout: "#bc8cff",
  flash_risk: "#f85149",
  low_vol_drift: "#8b949e",
  unknown: "#30363d",
};

export const REGIME_LABELS: Record<string, string> = {
  range: "Range",
  trend_up: "Trend ↑",
  trend_down: "Trend ↓",
  breakout: "Breakout",
  flash_risk: "Flash risk",
  low_vol_drift: "Low-vol drift",
  unknown: "Unknown",
};

export const regimeColor = (label: string) => REGIME_COLORS[label] ?? REGIME_COLORS.unknown;
export const regimeLabel = (label: string) => REGIME_LABELS[label] ?? label;
