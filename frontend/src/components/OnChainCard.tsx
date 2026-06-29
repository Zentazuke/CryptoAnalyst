import type { OnChain } from "../types";

const sign = (v: number | null | undefined, d = 0) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`;
const signColor = (v: number | null | undefined) =>
  v == null ? undefined : v > 0 ? "#3fb950" : v < 0 ? "#f85149" : undefined;
const compact = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 1 });

const divColor: Record<string, string> = { bullish: "#3fb950", bearish: "#f85149", none: "#8b949e" };

/** On-chain network activity + activity-vs-price divergence (free Coin Metrics). */
export function OnChainCard({ onchain }: { onchain: OnChain | null }) {
  if (!onchain || !onchain.available) {
    return (
      <div className="card">
        <div className="card-title">On-chain</div>
        <p className="muted-txt">
          No free on-chain coverage for this asset (Coin Metrics community tier — major assets only).
        </p>
      </div>
    );
  }
  const div = onchain.divergence ?? "none";
  const cal = onchain.divergence_calibration;
  return (
    <div className="card">
      <div className="card-title">On-chain · network activity</div>
      {div !== "none" && (
        <div className="crowd-read" style={{ borderColor: divColor[div], color: divColor[div] }}>
          {div === "bullish"
            ? "Bullish divergence: activity rising while price falls"
            : "Bearish divergence: activity fading while price rises"}
        </div>
      )}
      {cal && cal.hit_rate != null && (
        <p className="muted-txt" style={{ fontSize: 11.5, margin: "0 0 10px" }}>
          {cal.verdict === "edge" ? (
            <span style={{ color: "#3fb950" }}>
              Measured edge: divergence led price correctly {(cal.hit_rate * 100).toFixed(0)}% vs {((cal.base_rate ?? 0) * 100).toFixed(0)}% base (n={cal.n}, CI excludes baseline).
            </span>
          ) : (
            <>Measured: {(cal.hit_rate * 100).toFixed(0)}% vs {((cal.base_rate ?? 0) * 100).toFixed(0)}% base (n={cal.n}) — within noise, no significant edge on this asset.</>
          )}
        </p>
      )}
      <div className="stat-grid">
        <Stat label="Active addresses" value={compact(onchain.active_addresses)} />
        <Stat label="Addr 30d" value={sign(onchain.addr_trend_30d)} color={signColor(onchain.addr_trend_30d)} />
        <Stat label="Addr percentile" value={onchain.addr_percentile_90d != null ? `${(onchain.addr_percentile_90d * 100).toFixed(0)}th` : "—"} hint="vs the last 90 days" />
        <Stat label="Tx count" value={compact(onchain.tx_count)} />
        <Stat label="Tx 30d" value={sign(onchain.tx_trend_30d)} color={signColor(onchain.tx_trend_30d)} />
        <Stat label="Price 30d" value={sign(onchain.price_trend_30d)} color={signColor(onchain.price_trend_30d)} />
      </div>
    </div>
  );
}

function Stat({ label, value, color, hint }: { label: string; value: string; color?: string; hint?: string }) {
  return (
    <div className="stat" title={hint}>
      <span className="stat-k">{label}</span>
      <span className="stat-v" style={color ? { color } : undefined}>{value}</span>
    </div>
  );
}
