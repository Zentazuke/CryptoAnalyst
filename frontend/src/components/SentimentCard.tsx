import type { Sentiment } from "../types";

const biasColor = (label?: string) => {
  const l = (label ?? "").toLowerCase();
  if (l.includes("bull")) return "#3fb950";
  if (l.includes("bear")) return "#f85149";
  return "#8b949e";
};
const fgColor = (v?: number) =>
  v == null ? "#8b949e" : v <= 25 ? "#f85149" : v >= 75 ? "#f0883e" : v >= 55 ? "#3fb950" : "#c9d1d9";
const signColor = (v?: number | null) =>
  v == null ? undefined : v > 0 ? "#3fb950" : v < 0 ? "#f85149" : undefined;

const num = (v: number | null | undefined, d = 2, s = "") =>
  v == null ? "—" : `${v.toLocaleString(undefined, { maximumFractionDigits: d })}${s}`;
const signed = (v: number | null | undefined, d = 2, s = "") =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${num(v, d, s)}`;
const pct = (v: number | null | undefined, d = 0) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
const usd = (v?: number) => {
  if (v == null) return "—";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${v.toLocaleString()}`;
};
const hLabel = (s?: number) => (s === 3600 ? "1h" : s === 21600 ? "6h" : s === 86400 ? "24h" : s ? `${Math.round(s / 3600)}h` : "?");

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="stat">
      <span className="stat-k">{label}</span>
      <span className="stat-v" style={color ? { color } : undefined}>{value}</span>
    </div>
  );
}

/** Live sentiment from the engine — mirrors the sentiment dashboard's metrics. */
export function SentimentCard({ sentiment }: { sentiment: Sentiment | null }) {
  if (!sentiment || !sentiment.available) {
    return (
      <div className="card">
        <div className="card-title">Sentiment &amp; context</div>
        <p className="muted-txt">
          Sentiment engine offline. Start it (port 8787) for live outlook, Fear &amp; Greed,
          positioning, and news/social sentiment — the analyst runs fine without it.
        </p>
      </div>
    );
  }

  const ol = sentiment.outlook ?? {};
  const ctx = sentiment.context ?? {};
  const snap = sentiment.snapshot ?? {};
  const pos = sentiment.positioning ?? {};
  const dv = sentiment.derivatives ?? {};
  const ins = sentiment.insights ?? {};
  const color = biasColor(ol.label);
  const dp = ol.direction_prob_6h ?? sentiment.direction_prob_6h ?? null;
  const events = Array.isArray(sentiment.recent?.events) ? sentiment.recent!.events! : [];
  const terms = Array.isArray(ins.terms) ? ins.terms : [];
  // sources is a dict of {count, avg_sentiment}; skip non-object entries (e.g. "divergence": null)
  const sources = Object.entries(ins.sources ?? {}).filter(
    ([, v]) => v && typeof v === "object",
  ) as [string, { count?: number; avg_sentiment?: number }][];
  const crowdSignal = typeof pos.signal === "number" ? pos.signal.toFixed(2) : (pos.signal ?? "—");

  return (
    <div className="card">
      <div className="card-title">Sentiment &amp; context · live</div>

      <div className="regime-headline">
        <span className="regime-chip" style={{ background: color }} />
        <span className="regime-name" style={{ color, fontSize: 20 }}>{ol.label ?? "n/a"}</span>
        {ol.outlook_score != null && <span className="muted-txt">score {signed(ol.outlook_score)}</span>}
        {ol.context_tilt != null && <span className="muted-txt">· tilt {signed(ol.context_tilt)}</span>}
      </div>

      {/* multi-horizon outlook */}
      {ol.horizons && ol.horizons.length > 0 && (
        <div className="horizon-row">
          {ol.horizons.map((h, i) => (
            <span key={i} className="horizon-chip" style={{ borderColor: biasColor(h.label) }}>
              <b>{hLabel(h.horizon_seconds)}</b> {h.label ?? "—"}
              {h.score != null && <span className="muted-txt"> {signed(h.score)}</span>}
            </span>
          ))}
        </div>
      )}

      <h4 className="commentary-h">Market context</h4>
      <div className="stat-grid">
        <Stat label="Fear & Greed" value={ctx.fear_greed_value != null ? `${ctx.fear_greed_value.toFixed(0)}${ctx.fear_greed_label ? ` (${ctx.fear_greed_label})` : ""}` : "—"} color={fgColor(ctx.fear_greed_value)} />
        <Stat label="BTC dominance" value={num(ctx.btc_dominance_pct, 1, "%")} />
        <Stat label="Mkt cap 24h" value={signed(ctx.market_cap_change_24h_pct, 1, "%")} color={signColor(ctx.market_cap_change_24h_pct)} />
        <Stat label="Outlook conf." value={pct(ol.confidence)} />
        <Stat label="6h up-prob" value={pct(dp)} color={dp == null ? undefined : dp >= 0.5 ? "#3fb950" : "#f85149"} />
      </div>

      <h4 className="commentary-h">Sentiment activity</h4>
      <div className="stat-grid">
        <Stat label="Avg sentiment" value={signed(snap.average_sentiment)} color={signColor(snap.average_sentiment)} />
        <Stat label="Velocity" value={signed(snap.sentiment_velocity)} color={signColor(snap.sentiment_velocity)} />
        <Stat label="Attention" value={num(snap.attention_spike)} />
        <Stat label="Data quality" value={pct(snap.data_quality)} />
        <Stat label="Messages" value={num(snap.message_count, 0)} />
      </div>

      <h4 className="commentary-h">Positioning &amp; derivatives</h4>
      {(() => {
        const ratio = pos.global_account_ratio;
        const fr = dv.funding_rate;
        const longC = (ratio != null && ratio >= 1.5) || (fr != null && fr >= 0.0002);
        const shortC = (ratio != null && ratio <= 0.67) || (fr != null && fr <= -0.0002);
        if (!longC && !shortC) return ratio != null || fr != null
          ? <div className="crowd-read" style={{ borderColor: "#8b949e", color: "#8b949e" }}>Crowd read: balanced</div> : null;
        const bear = longC && !shortC;
        return (
          <div className="crowd-read" style={{ borderColor: bear ? "#f85149" : "#3fb950", color: bear ? "#f85149" : "#3fb950" }}>
            Crowd read: {bear ? "crowded long → contrarian-bearish" : "crowded short → contrarian-bullish"}
          </div>
        );
      })()}
      <div className="stat-grid">
        <Stat label="Crowd signal" value={crowdSignal} />
        <Stat label="Global L/S" value={num(pos.global_account_ratio)} />
        <Stat label="Taker ratio" value={num(pos.taker_ratio)} />
        <Stat label="Funding (8h)" value={dv.funding_rate != null ? `${signed(dv.funding_rate * 100, 4)}%` : "—"} color={signColor(dv.funding_rate)} />
        <Stat label="Open interest" value={usd(dv.open_interest_usd)} />
      </div>

      {(terms.length > 0 || sources.length > 0) && (
        <>
          <h4 className="commentary-h">Insights{ins.event_count != null ? ` · ${ins.event_count} events` : ""}</h4>
          {terms.length > 0 && (
            <div className="term-chips">
              {terms.slice(0, 12).map((t, i) => (
                <span key={i} className="term-chip">{t?.term ?? String(t)}{t?.count ? ` ·${t.count}` : ""}</span>
              ))}
            </div>
          )}
          {sources.length > 0 && (
            <div className="src-row">
              {sources.map(([name, s]) => (
                <span key={name} className="src-item">
                  {name}: <b style={{ color: signColor(s?.avg_sentiment) }}>{signed(s?.avg_sentiment)}</b>
                  <span className="muted-txt"> ({s?.count ?? 0})</span>
                </span>
              ))}
            </div>
          )}
        </>
      )}

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
