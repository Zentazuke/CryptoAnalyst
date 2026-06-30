import type { CarryRead } from "../types";

/** Funding-carry read — a real observable (delta-neutral basis yield), framed
 *  honestly as context, not alpha. Shown for any symbol with funding history. */
export function CarryCard({ carry }: { carry: CarryRead | null }) {
  if (!carry) return null;
  const pos = carry.carry_annual_pct >= 0;
  const color = pos ? "#3fb950" : "#f85149";
  const pctl = carry.percentile;
  return (
    <div className="card carry">
      <div className="card-title">
        Funding carry · {carry.symbol.replace("_", "/")} <span className="muted-txt">· delta-neutral basis yield</span>
      </div>
      <div className="vrp-grid">
        <div className="vrp-stat">
          <span className="vrp-k">Annualized carry</span>
          <span className="vrp-v" style={{ color }}>{pos ? "+" : ""}{carry.carry_annual_pct}%</span>
        </div>
        <div className="vrp-stat">
          <span className="vrp-k">Current funding (8h)</span>
          <span className="vrp-v">{carry.current_funding_8h_pct >= 0 ? "+" : ""}{carry.current_funding_8h_pct}%</span>
        </div>
        <div className="vrp-stat">
          <span className="vrp-k">Percentile</span>
          <span className="vrp-v">{pctl != null ? `${(pctl * 100).toFixed(0)}th` : "—"}</span>
        </div>
        <div className="vrp-stat">
          <span className="vrp-k">Trend</span>
          <span className="vrp-v" style={{ color: carry.compressing ? "#d29922" : "#3fb950", fontSize: 14 }}>
            {carry.compressing ? "compressing" : "firm"}
          </span>
        </div>
      </div>
      <p className="vrp-trade muted-txt">⚠ Context, not alpha: {carry.note}</p>
    </div>
  );
}
