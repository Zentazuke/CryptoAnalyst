import type { VrpRead, VrpJournalResponse } from "../types";

const VERDICT: Record<string, { color: string; label: string }> = {
  rich: { color: "#3fb950", label: "RICH — well-paid to sell" },
  fair: { color: "#d29922", label: "FAIR — marginal" },
  cheap: { color: "#f85149", label: "CHEAP — stand aside" },
};

/** Live variance-risk-premium read — the cockpit for the one validated edge.
 *  Frames (not predicts) the current implied-vs-realized spread and whether
 *  it's rich enough to sell vol, defined-risk. BTC/ETH only. */
export function VrpCard({ vrp, journal }: { vrp: VrpRead | null; journal?: VrpJournalResponse | null }) {
  if (!vrp) return null;
  const jv = journal?.by_verdict ?? {};
  const matured = Object.values(jv).reduce((s, x) => s + x.n, 0);
  const v = VERDICT[vrp.verdict] ?? VERDICT.fair;
  const pctl = Math.max(0, Math.min(1, vrp.premium_percentile));

  return (
    <div className="card vrp">
      <div className="card-title">
        Volatility risk premium · {vrp.currency} <span className="muted-txt">· premium gauge (context, not a trade)</span>
      </div>

      <div className="vrp-head">
        <span className="vrp-verdict" style={{ color: v.color, borderColor: v.color }}>{v.label}</span>
        <span className="muted-txt" style={{ fontSize: 12 }}>
          premium {vrp.premium_volpts >= 0 ? "+" : ""}{vrp.premium_volpts} vol-pts · {(pctl * 100).toFixed(0)}th percentile
        </span>
      </div>

      <div className="vrp-grid">
        <div className="vrp-stat"><span className="vrp-k">Implied (DVOL 30d)</span><span className="vrp-v">{vrp.implied_vol_dvol}%</span></div>
        <div className="vrp-stat"><span className="vrp-k">Realized (30d)</span><span className="vrp-v">{vrp.realized_vol_30d}%</span></div>
        <div className="vrp-stat"><span className="vrp-k">Premium</span><span className="vrp-v" style={{ color: vrp.premium_volpts > 0 ? "#3fb950" : "#f85149" }}>{vrp.premium_volpts >= 0 ? "+" : ""}{vrp.premium_volpts}</span></div>
        <div className="vrp-stat"><span className="vrp-k">Median premium</span><span className="vrp-v">{vrp.premium_median >= 0 ? "+" : ""}{vrp.premium_median}</span></div>
      </div>

      {/* percentile meter: how rich is the premium vs its own ~5y history */}
      <div className="vrp-meter" title={`current premium at the ${(pctl * 100).toFixed(0)}th percentile of ${vrp.samples} days`}>
        <div className="vrp-meter-fill" style={{ width: `${pctl * 100}%`, background: v.color }} />
      </div>
      <div className="vrp-meter-labels"><span>cheap (don't sell)</span><span>rich (sell defined-risk)</span></div>

      <p className="vrp-rec">{vrp.recommendation}</p>
      <p className="vrp-trade muted-txt">
        ⚠ Context, not a trade signal: {vrp.trade.note} See VRP_MODEL_CARD.md.
      </p>

      {journal && (
        <div className="vrp-journal">
          <span className="vrp-k">Live signal journal</span>
          {journal.count === 0 ? (
            <span className="muted-txt"> — accruing; it logs the read daily and outcomes mature in 30d.</span>
          ) : matured === 0 ? (
            <span className="muted-txt"> — {journal.count} logged; first outcomes mature in 30d.</span>
          ) : (
            <span className="muted-txt">
              {" "}({matured} matured):{" "}
              {["rich", "fair", "cheap"].filter((v) => jv[v]).map((v) => (
                <span key={v}> {v} {jv[v].mean_pnl_volpts >= 0 ? "+" : ""}{jv[v].mean_pnl_volpts} vol-pts ({(jv[v].hit_rate * 100).toFixed(0)}% pos, n={jv[v].n}) ·</span>
              ))}{" "}
              <i>"rich" should beat "cheap" if the signal is real.</i>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
