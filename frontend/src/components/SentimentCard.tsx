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

function Stat({ label, value, color, hint }: { label: string; value: string; color?: string; hint?: string }) {
  return (
    <div className="stat" title={hint}>
      <span className="stat-k">{label}</span>
      <span className="stat-v" style={color ? { color } : undefined}>{value}</span>
    </div>
  );
}

function SubHead({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="sent-subhead">
      <h4 className="commentary-h" style={{ margin: 0 }}>{title}</h4>
      <span className="sent-hint">{hint}</span>
    </div>
  );
}

/** Live sentiment from the engine — mirrors the sentiment dashboard's metrics,
 *  reorganised into labeled groups with a plain-English read up top. */
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

  // crowd-positioning read, computed once and reused in the summary + box
  const crowd = (() => {
    const ratio = pos.global_account_ratio;
    const fr = dv.funding_rate;
    const longC = (ratio != null && ratio >= 1.5) || (fr != null && fr >= 0.0002);
    const shortC = (ratio != null && ratio <= 0.67) || (fr != null && fr <= -0.0002);
    if (longC && !shortC) return { text: "crowded long → contrarian-bearish", tone: "#f85149" };
    if (shortC && !longC) return { text: "crowded short → contrarian-bullish", tone: "#3fb950" };
    if (ratio != null || fr != null) return { text: "balanced — no crowding", tone: "#8b949e" };
    return null;
  })();

  // one-line synthesis so you don't have to read the grid to get the gist
  const summary = (() => {
    const bits: string[] = [];
    if (ol.label) bits.push(`engine reads ${ol.label.toLowerCase()}${ol.confidence != null ? ` (${pct(ol.confidence)} conf)` : ""}`);
    if (dp != null) bits.push(`6h up-probability ${pct(dp)}`);
    if (ctx.fear_greed_value != null) bits.push(`Fear & Greed ${ctx.fear_greed_value.toFixed(0)}${ctx.fear_greed_label ? ` — ${ctx.fear_greed_label.toLowerCase()}` : ""}`);
    if (crowd) bits.push(`positioning ${crowd.text}`);
    return bits.length ? `${bits.join("; ")}.` : null;
  })();

  return (
    <div className="card">
      <div className="card-title">Sentiment &amp; context · live</div>

      <div className="regime-headline" style={{ flexWrap: "wrap", marginBottom: 8 }}>
        <span className="regime-chip" style={{ background: color }} />
        <span className="regime-name" style={{ color, fontSize: 20 }}>{ol.label ?? "n/a"}</span>
        {ol.outlook_score != null && <span className="muted-txt">score {signed(ol.outlook_score)}</span>}
        {ol.context_tilt != null && <span className="muted-txt">· macro tilt {signed(ol.context_tilt)}</span>}
        {ol.confidence != null && <span className="muted-txt">· {pct(ol.confidence)} conf</span>}
      </div>

      {summary && <p className="sent-summary" style={{ borderLeftColor: color }}>{summary}</p>}

      {/* multi-horizon outlook */}
      {ol.horizons && ol.horizons.length > 0 && (
        <>
          <SubHead title="Directional outlook" hint="engine's blended lean per horizon" />
          <div className="horizon-row">
            {ol.horizons.map((h, i) => (
              <span key={i} className="horizon-chip" style={{ borderColor: biasColor(h.label) }}>
                <b>{hLabel(h.horizon_seconds)}</b> {h.label ?? "—"}
                {h.score != null && <span className="muted-txt"> {signed(h.score)}</span>}
              </span>
            ))}
          </div>
        </>
      )}

      <SubHead title="Market context" hint="the broad-market backdrop today" />
      <div className="stat-grid">
        <Stat label="Fear & Greed" value={ctx.fear_greed_value != null ? `${ctx.fear_greed_value.toFixed(0)}${ctx.fear_greed_label ? ` (${ctx.fear_greed_label})` : ""}` : "—"} color={fgColor(ctx.fear_greed_value)} hint="0 = extreme fear, 100 = extreme greed" />
        <Stat label="BTC dominance" value={num(ctx.btc_dominance_pct, 1, "%")} hint="BTC share of total crypto market cap" />
        <Stat label="Mkt cap 24h" value={signed(ctx.market_cap_change_24h_pct, 1, "%")} color={signColor(ctx.market_cap_change_24h_pct)} hint="total crypto market cap change, 24h" />
        <Stat label="Outlook conf." value={pct(ol.confidence)} hint="engine's confidence in its directional read" />
        <Stat label="6h up-prob" value={pct(dp)} color={dp == null ? undefined : dp >= 0.5 ? "#3fb950" : "#f85149"} hint="modeled probability price is higher in 6h — live-only source, not yet calibrated over history" />
      </div>
      <p className="sent-hint" style={{ margin: "2px 2px 0" }}>
        Note: the engine's 6h up-probability comes from a live-only feed, so it carries no historical track record yet — treat it as context, not a measured edge.
      </p>

      <SubHead title="Social & news activity" hint="what the crowd is saying right now" />
      <div className="stat-grid">
        <Stat label="Avg sentiment" value={signed(snap.average_sentiment)} color={signColor(snap.average_sentiment)} hint="mean tone of messages (−1 to +1)" />
        <Stat label="Velocity" value={signed(snap.sentiment_velocity)} color={signColor(snap.sentiment_velocity)} hint="how fast sentiment is shifting" />
        <Stat label="Attention" value={num(snap.attention_spike)} hint="chatter volume vs normal (1 = baseline)" />
        <Stat label="Data quality" value={pct(snap.data_quality)} hint="confidence in the sentiment sample" />
        <Stat label="Messages" value={num(snap.message_count, 0)} hint="messages in the sample window" />
      </div>

      <SubHead title="Positioning & derivatives" hint="how leveraged traders sit — contrarian when crowded" />
      {crowd && (
        <div className="crowd-read" style={{ borderColor: crowd.tone, color: crowd.tone }}>
          Crowd read: {crowd.text}
        </div>
      )}
      <div className="stat-grid">
        <Stat label="Crowd signal" value={crowdSignal} hint="engine's positioning signal" />
        <Stat label="Global L/S" value={num(pos.global_account_ratio)} hint="long/short account ratio; >1 = more longs" />
        <Stat label="Taker ratio" value={num(pos.taker_ratio)} hint="aggressive buy vs sell flow" />
        <Stat label="Funding (8h)" value={dv.funding_rate != null ? `${signed(dv.funding_rate * 100, 4)}%` : "—"} color={signColor(dv.funding_rate)} hint="positive = longs pay shorts (long-heavy)" />
        <Stat label="Open interest" value={usd(dv.open_interest_usd)} hint="total notional in open perp positions" />
      </div>

      {(terms.length > 0 || sources.length > 0) && (
        <>
          <SubHead title="Insights" hint={`trending terms${ins.event_count != null ? ` · ${ins.event_count} events tracked` : ""}`} />
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
        <>
          <SubHead title="Recent headlines" hint="latest scored news & social posts" />
          <ul className="headline-list">
            {events.slice(0, 4).map((e, i) => (
              <li key={i}>
                <span className="headline-dot" style={{ background: (e.score ?? 0) > 0 ? "#3fb950" : (e.score ?? 0) < 0 ? "#f85149" : "#8b949e" }} />
                <span className="headline-txt">{e.text}</span>
                {e.source && <span className="muted-txt headline-src">{e.source}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
