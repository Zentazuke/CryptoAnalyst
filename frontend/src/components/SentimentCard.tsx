import type { Sentiment } from "../types";

const biasColor = (label?: string) => {
  const l = (label ?? "").toLowerCase();
  if (l.includes("bull")) return "#3fb950";
  if (l.includes("bear")) return "#f85149";
  return "#8b949e";
};

const fgColor = (v?: number) =>
  v == null ? "#8b949e" : v <= 25 ? "#f85149" : v >= 75 ? "#f0883e" : v >= 55 ? "#3fb950" : "#c9d1d9";

const num = (v: number | null | undefined, d = 2, s = "") =>
  v == null ? "—" : `${v.toLocaleString(undefined, { maximumFractionDigits: d })}${s}`;

/** Live sentiment from the sentiment engine: outlook, context, alerts, headlines. */
export function SentimentCard({ sentiment }: { sentiment: Sentiment | null }) {
  if (!sentiment || !sentiment.available) {
    return (
      <div className="card">
        <div className="card-title">Sentiment &amp; context</div>
        <p className="muted-txt">
          Sentiment engine offline. Start it (port 8787) for live outlook, Fear &amp; Greed, and
          news/social sentiment — the analyst runs fine without it.
        </p>
      </div>
    );
  }

  const ol = sentiment.outlook ?? {};
  const ctx = sentiment.context ?? {};
  const color = biasColor(ol.label);
  const dp = ol.direction_prob_6h ?? sentiment.direction_prob_6h ?? null;
  const events = sentiment.recent?.events ?? [];

  return (
    <div className="card">
      <div className="card-title">Sentiment &amp; context · live</div>

      <div className="regime-headline">
        <span className="regime-chip" style={{ background: color }} />
        <span className="regime-name" style={{ color, fontSize: 20 }}>
          {ol.label ?? "n/a"}
        </span>
        {ol.outlook_score != null && (
          <span className="muted-txt">score {ol.outlook_score >= 0 ? "+" : ""}{num(ol.outlook_score)}</span>
        )}
      </div>

      <div className="stat-grid">
        <Stat label="Fear & Greed" value={ctx.fear_greed_value != null ? `${ctx.fear_greed_value.toFixed(0)}${ctx.fear_greed_label ? ` (${ctx.fear_greed_label})` : ""}` : "—"} color={fgColor(ctx.fear_greed_value)} />
        <Stat label="BTC dominance" value={num(ctx.btc_dominance_pct, 1, "%")} />
        <Stat label="Mkt cap 24h" value={ctx.market_cap_change_24h_pct != null ? `${ctx.market_cap_change_24h_pct >= 0 ? "+" : ""}${num(ctx.market_cap_change_24h_pct, 1)}%` : "—"} />
        <Stat label="Outlook conf." value={ol.confidence != null ? `${(ol.confidence * 100).toFixed(0)}%` : "—"} />
        <Stat label="6h up-prob" value={dp != null ? `${(dp * 100).toFixed(0)}%` : "—"} color={dp == null ? undefined : dp >= 0.5 ? "#3fb950" : "#f85149"} />
      </div>

      {events.length > 0 && (
        <div className="headlines">
          <h4 className="commentary-h">Recent headlines</h4>
          <ul className="headline-list">
            {events.slice(0, 4).map((e, i) => (
              <li key={i}>
                <span className="headline-dot" style={{ background: (e.score ?? 0) > 0 ? "#3fb950" : (e.score ?? 0) < 0 ? "#f85149" : "#8b949e" }} />
                <span className="headline-txt">{e.text}</span>
                {e.source && <span className="muted-txt headline-src">{e.source}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="stat">
      <span className="stat-k">{label}</span>
      <span className="stat-v" style={color ? { color } : undefined}>{value}</span>
    </div>
  );
}
