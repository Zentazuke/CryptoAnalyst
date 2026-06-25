import type { ChartResponse } from "../types";

/** Makes the trust layer visible: where the data came from, how fresh it is,
 *  whether quality checks passed, and which indicator version produced it. */
export function TrustBar({ data, timeframe }: { data: ChartResponse; timeframe: string }) {
  const ageMs = Date.now() - new Date(data.last_candle).getTime();
  const ageHours = ageMs / 3_600_000;
  const tfHours = timeframeHours(timeframe);
  // fresh if within ~2 bars of the latest expected candle
  const fresh = tfHours > 0 ? ageHours <= tfHours * 2 + 0.1 : true;

  const q = data.quality;
  const qGood = q?.status === "pass";

  return (
    <div className="trustbar">
      <div className="trust-item">
        <span className="k">Source</span>
        <span className="v">{data.source}</span>
      </div>
      <div className="trust-item">
        <span className="k">Last candle</span>
        <span className="v">{new Date(data.last_candle).toLocaleString()}</span>
      </div>
      <div className="trust-item">
        <span className="k">Freshness</span>
        <span className="v">
          <span className={`badge ${fresh ? "good" : "warn"}`}>
            <span className={`dot ${fresh ? "good" : "warn"}`} />
            {fresh ? "fresh" : "stale"} · {formatAge(ageMs)}
          </span>
        </span>
      </div>
      <div className="trust-item">
        <span className="k">Data quality</span>
        <span className="v">
          <span className={`badge ${qGood ? "good" : q ? "bad" : "warn"}`}>
            <span className={`dot ${qGood ? "good" : q ? "bad" : "warn"}`} />
            {q ? `${q.status} — ${q.detail}` : "no check"}
          </span>
        </span>
      </div>
      <div className="trust-item">
        <span className="k">Bars</span>
        <span className="v">{data.bars}</span>
      </div>
      <div className="trust-item">
        <span className="k">Indicator engine</span>
        <span className="v">v{data.indicator_version}</span>
      </div>
    </div>
  );
}

function timeframeHours(tf: string): number {
  const map: Record<string, number> = {
    "1m": 1 / 60, "5m": 5 / 60, "15m": 15 / 60, "30m": 30 / 60,
    "1h": 1, "4h": 4, "12h": 12, "1D": 24, "7D": 168,
  };
  return map[tf] ?? 0;
}

function formatAge(ms: number): string {
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}
