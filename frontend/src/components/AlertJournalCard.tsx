import type { AlertJournalResponse } from "../types";

const dirColor = (d: string) => (d === "bull" ? "#3fb950" : d === "bear" ? "#f85149" : "#8b949e");
const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

/** Live track record: alerts that have fired, and how they've done since. */
export function AlertJournalCard({
  data, onPick,
}: {
  data: AlertJournalResponse | null;
  onPick?: (instrument: string) => void;
}) {
  if (!data || data.count === 0) {
    return (
      <div className="card">
        <div className="card-title">Alert journal</div>
        <p className="muted-txt">No alerts journaled yet — they accrue as alerts fire over time.</p>
      </div>
    );
  }
  return (
    <div className="card">
      <div className="card-title">
        Alert journal · {data.count} fired
        {data.on_track_rate != null && (
          <span style={{ color: data.on_track_rate >= 0.5 ? "#3fb950" : "#f85149" }}>
            {" "}· {(data.on_track_rate * 100).toFixed(0)}% on track
          </span>
        )}
      </div>
      <ul className="alert-list">
        {data.alerts.slice(0, 12).map((a, i) => (
          <li
            key={i}
            className={onPick ? "alert-item clickable" : "alert-item"}
            style={{ borderLeftColor: dirColor(a.direction) }}
            onClick={() => onPick?.(`${a.symbol}USDT`)}
          >
            <span className="muted-txt journal-when">{when(a.fired_at)}</span>
            <b style={{ color: dirColor(a.direction) }}>{a.symbol}</b>
            <span className="alert-kind">{a.kind}</span>
            <span className="alert-note">
              {a.since_ret != null ? `${a.since_ret >= 0 ? "+" : ""}${(a.since_ret * 100).toFixed(1)}% since` : "—"}
            </span>
            {a.on_track != null && (
              <span style={{ color: a.on_track ? "#3fb950" : "#f85149", fontSize: 11 }}>
                {a.on_track ? "on track" : "off"}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
