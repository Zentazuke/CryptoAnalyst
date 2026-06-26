import type { MetricRead } from "../types";

const BIAS_COLOR: Record<string, string> = {
  bullish: "#3fb950",
  bearish: "#f85149",
  neutral: "#8b949e",
  directional: "#bc8cff",
  "high-risk": "#f0883e",
};

/** Focused, per-metric analyst reads — each signal read on its own:
 *  what it shows, what it means, and where it might go based on that metric. */
export function MetricBreakdown({ reads }: { reads?: MetricRead[] }) {
  if (!reads || reads.length === 0) return null;
  return (
    <div className="metric-grid">
      {reads.map((r) => {
        const color = BIAS_COLOR[r.bias ?? "neutral"] ?? "#8b949e";
        return (
          <div key={r.key} className="metric-read" style={{ borderLeftColor: color }}>
            <div className="metric-read-head">
              <span className="metric-read-title">{r.title}</span>
              {r.bias && (
                <span className="metric-read-bias" style={{ color, borderColor: color }}>
                  {r.bias}
                </span>
              )}
            </div>
            <p className="metric-read-reading">{r.reading}</p>
            <p className="metric-read-row"><span className="metric-read-k">Means</span>{r.meaning}</p>
            <p className="metric-read-row"><span className="metric-read-k">Outlook</span>{r.outlook}</p>
          </div>
        );
      })}
    </div>
  );
}
