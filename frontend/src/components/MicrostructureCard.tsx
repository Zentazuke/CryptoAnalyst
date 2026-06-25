import type { MicroSnapshot } from "../types";

const fmt = (n: number | null | undefined, digits = 2, suffix = "") =>
  n == null ? "—" : `${n.toLocaleString(undefined, { maximumFractionDigits: digits })}${suffix}`;

/** Latest order-book + derivatives snapshot (point-in-time). */
export function MicrostructureCard({ micro }: { micro: MicroSnapshot | null }) {
  if (!micro) {
    return (
      <div className="card">
        <div className="card-title">Microstructure</div>
        <p className="muted-txt">
          No snapshot yet. Run <code>python -m analyst.collect_micro</code> (the launcher does this
          automatically).
        </p>
      </div>
    );
  }

  const totalDepth = micro.bid_depth_quote + micro.ask_depth_quote;
  const imbalance = totalDepth > 0 ? (micro.bid_depth_quote - micro.ask_depth_quote) / totalDepth : 0;
  const fundingPct = micro.funding_rate != null ? micro.funding_rate * 100 : null;

  return (
    <div className="card">
      <div className="card-title">
        Microstructure <span className="muted-txt">· {new Date(micro.snapshot_time).toLocaleString()}</span>
      </div>
      <div className="stat-grid">
        <Stat label="Spread" value={fmt(micro.spread_bps, 3, " bps")} />
        <Stat label="Mid" value={fmt(micro.mid, 2)} />
        <Stat
          label={`Depth ±${micro.depth_band_bps}bps`}
          value={`${fmt(micro.bid_depth_quote, 0)} / ${fmt(micro.ask_depth_quote, 0)}`}
          hint="bid / ask quote notional"
        />
        <Stat
          label="Book imbalance"
          value={`${(imbalance * 100).toFixed(1)}%`}
          tone={imbalance > 0.05 ? "good" : imbalance < -0.05 ? "bad" : undefined}
        />
        <Stat label="Open interest" value={fmt(micro.open_interest, 1)} />
        <Stat
          label="Funding"
          value={fundingPct == null ? "—" : `${fundingPct >= 0 ? "+" : ""}${fundingPct.toFixed(4)}%`}
          tone={fundingPct == null ? undefined : fundingPct > 0 ? "good" : fundingPct < 0 ? "bad" : undefined}
          hint="longs pay shorts when positive"
        />
        <Stat
          label="Basis"
          value={fmt(micro.basis_bps, 2, " bps")}
          tone={micro.basis_bps == null ? undefined : micro.basis_bps > 0 ? "good" : "bad"}
        />
      </div>
    </div>
  );
}

function Stat({ label, value, hint, tone }: {
  label: string; value: string; hint?: string; tone?: "good" | "bad";
}) {
  return (
    <div className="stat" title={hint}>
      <span className="stat-k">{label}</span>
      <span className={`stat-v ${tone ? tone + "-txt" : ""}`}>{value}</span>
    </div>
  );
}
