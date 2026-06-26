import type { Commentary } from "../types";

const BIAS_COLOR: Record<string, string> = {
  bullish: "#3fb950",
  bearish: "#f85149",
  neutral: "#8b949e",
  directional: "#bc8cff",
  "high-risk": "#f0883e",
};

/** The written analyst note: headline, observations, interpretation, outlook. */
export function CommentaryCard({ note }: { note: Commentary }) {
  const color = BIAS_COLOR[note.outlook.bias] ?? "#8b949e";
  return (
    <div className="card commentary">
      <div className="card-title">Analyst note</div>
      <p className="commentary-headline">{note.headline}</p>

      <div className="commentary-cols">
        <div>
          <h4 className="commentary-h">What's happening</h4>
          <ul className="commentary-list">
            {note.whats_happening.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
        <div>
          <h4 className="commentary-h">What it means</h4>
          <ul className="commentary-list">
            {note.what_it_means.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      </div>

      <div className="outlook-box" style={{ borderColor: color }}>
        <div className="outlook-head">
          <span className="outlook-badge" style={{ background: color }}>
            {note.outlook.bias} · {note.outlook.confidence} conviction
          </span>
          <span className="muted-txt">outlook</span>
        </div>
        <p className="outlook-text">{note.outlook.text}</p>
        {note.outlook.invalidation && (
          <p className="outlook-inval"><b>Invalidation:</b> {note.outlook.invalidation}</p>
        )}
      </div>

      {note.risk && (
        <div className="risk-strip">
          <span className="risk-item">
            <span className="risk-k">Expected move</span>
            <span className="risk-v">±{(note.risk.expected_move_pct * 100).toFixed(1)}%</span>
          </span>
          <span className="risk-item">
            <span className="risk-k">Range</span>
            <span className="risk-v">{note.risk.band_low.toLocaleString()}–{note.risk.band_high.toLocaleString()}</span>
          </span>
          <span className="risk-item">
            <span className="risk-k">Volatility</span>
            <span className="risk-v" style={{ color: note.risk.vol_regime === "compressed" ? "#d29922" : note.risk.vol_regime === "elevated" ? "#f0883e" : undefined }}>
              {note.risk.vol_regime}
            </span>
          </span>
          <span className="risk-item">
            <span className="risk-k">1-ATR risk</span>
            <span className="risk-v">{(note.risk.atr_pct * 100).toFixed(1)}%</span>
          </span>
          <span className="risk-item">
            <span className="risk-k">R to resistance</span>
            <span className="risk-v" style={{ color: "#3fb950" }}>{note.risk.long.rr != null ? `${note.risk.long.rr.toFixed(1)}R` : "—"}</span>
          </span>
          <span className="risk-item">
            <span className="risk-k">R to support</span>
            <span className="risk-v" style={{ color: "#f85149" }}>{note.risk.short.rr != null ? `${note.risk.short.rr.toFixed(1)}R` : "—"}</span>
          </span>
          {note.risk.implied_vol && (
            <span className="risk-item" title={`realized ${note.risk.implied_vol.realized_vol_annual.toFixed(0)}%`}>
              <span className="risk-k">Implied vol (DVOL)</span>
              <span className="risk-v" style={{ color: note.risk.implied_vol.signal === "premium" ? "#f0883e" : note.risk.implied_vol.signal === "discount" ? "#3fb950" : undefined }}>
                {note.risk.implied_vol.dvol.toFixed(0)}% ({note.risk.implied_vol.premium_pts >= 0 ? "+" : ""}{note.risk.implied_vol.premium_pts.toFixed(0)})
              </span>
            </span>
          )}
        </div>
      )}

      {note.caveat && <p className="commentary-caveat">{note.caveat}</p>}
    </div>
  );
}
