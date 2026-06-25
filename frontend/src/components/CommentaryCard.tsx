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

      {note.caveat && <p className="commentary-caveat">{note.caveat}</p>}
    </div>
  );
}
