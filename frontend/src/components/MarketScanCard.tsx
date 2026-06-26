import type { ScanResponse } from "../types";
import { regimeColor, regimeLabel } from "../regime";

const breadthColor = (b: string) => (b === "risk-on" ? "#3fb950" : b === "risk-off" ? "#f85149" : "#8b949e");
const momColor = (m: number) => (m > 0 ? "#3fb950" : m < 0 ? "#f85149" : "#c9d1d9");
const kindColor: Record<string, string> = {
  leader: "#3fb950", "crowded-long": "#f85149", "crowded-short": "#3fb950", oversold: "#d29922",
};
const pct = (v: number) => `${(v * 100).toFixed(0)}%`;
const fund = (v: number | null) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(3)}%`);

/** Market-wide breadth + relative-strength ranking + standout setups. */
export function MarketScanCard({
  scan, loading, onRefresh, onPick,
}: {
  scan: ScanResponse | null;
  loading: boolean;
  onRefresh: () => void;
  onPick?: (instrument: string) => void;
}) {
  return (
    <div className="card scan-card">
      <div className="card-title scan-head">
        <span>Market scan{scan ? ` · ${scan.count} coins · ${scan.timeframe}` : ""}</span>
        <button className="scan-refresh" onClick={onRefresh} disabled={loading}>
          {loading ? "scanning…" : "↻ rescan"}
        </button>
      </div>

      {!scan && !loading && <p className="muted-txt">Scan unavailable (needs the Binance source + API).</p>}

      {scan && (
        <>
          <div className="scan-breadth">
            <span className="badge" style={{ background: `${breadthColor(scan.aggregates.breadth)}22`, color: breadthColor(scan.aggregates.breadth) }}>
              {scan.aggregates.breadth}
            </span>
            <span className="muted-txt">{pct(scan.aggregates.pct_uptrend)} uptrend · {pct(scan.aggregates.pct_above_ema20)} above EMA20</span>
            {scan.aggregates.avg_funding != null && (
              <span className="muted-txt">· avg funding {fund(scan.aggregates.avg_funding)}</span>
            )}
            {scan.aggregates.rotation && (
              <span className="badge" style={{ background: "rgba(88,166,255,0.12)", color: "#58a6ff" }}>
                {scan.aggregates.rotation}
              </span>
            )}
          </div>

          {scan.setups.length > 0 && (
            <div className="scan-setups">
              {scan.setups.map((s, i) => (
                <span key={i} className="setup-chip" style={{ borderColor: kindColor[s.kind] ?? "#8b949e" }}>
                  <b style={{ color: kindColor[s.kind] ?? "#c9d1d9" }}>{s.symbol}</b> {s.note}
                </span>
              ))}
            </div>
          )}

          <div className="scan-table-wrap">
            <table className="scan-table">
              <thead>
                <tr><th>#</th><th>Coin</th><th>Regime</th><th className="r">Mom.</th><th className="r">vs BTC</th><th className="r">RSI</th><th className="r">ADX</th><th className="r">Funding</th></tr>
              </thead>
              <tbody>
                {scan.rows.slice(0, 18).map((r) => (
                  <tr key={r.instrument} className={onPick ? "clickable" : ""} onClick={() => onPick?.(r.instrument)}>
                    <td className="muted-txt">{r.rank}</td>
                    <td><b>{r.symbol}</b></td>
                    <td style={{ color: regimeColor(r.regime) }}>{regimeLabel(r.regime)}</td>
                    <td className="r" style={{ color: momColor(r.momentum) }}>{r.momentum >= 0 ? "+" : ""}{(r.momentum * 100).toFixed(1)}%</td>
                    <td className="r" style={{ color: r.rs_vs_btc == null ? undefined : momColor(r.rs_vs_btc) }}>{r.rs_vs_btc == null ? "—" : `${r.rs_vs_btc >= 0 ? "+" : ""}${(r.rs_vs_btc * 100).toFixed(1)}%`}</td>
                    <td className="r">{r.rsi != null ? r.rsi.toFixed(0) : "—"}</td>
                    <td className="r">{r.adx != null ? r.adx.toFixed(0) : "—"}</td>
                    <td className="r" style={{ color: r.funding == null ? undefined : r.funding > 0 ? "#3fb950" : "#f85149" }}>{fund(r.funding)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
