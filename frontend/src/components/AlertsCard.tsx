import type { AlertsResponse } from "../types";

const dirColor = (d: string) => (d === "bull" ? "#3fb950" : d === "bear" ? "#f85149" : "#8b949e");

/** Confluence-ranked setups across the market. Click to load the coin. */
export function AlertsCard({
  data, onPick,
}: {
  data: AlertsResponse | null;
  onPick?: (instrument: string) => void;
}) {
  const alerts = data?.alerts ?? [];
  if (alerts.length === 0) {
    return (
      <div className="card">
        <div className="card-title">Alerts</div>
        <p className="muted-txt">No multi-signal setups across the scanned market right now.</p>
      </div>
    );
  }
  return (
    <div className="card">
      <div className="card-title">Alerts · {alerts.length} confluence setups</div>
      <ul className="alert-list">
        {alerts.map((a, i) => (
          <li
            key={i}
            className={onPick ? "alert-item clickable" : "alert-item"}
            style={{ borderLeftColor: dirColor(a.direction) }}
            onClick={() => onPick?.(`${a.symbol}USDT`)}
          >
            <span className="alert-sev" title={`${a.severity} corroborating signals`}>
              {"●".repeat(Math.min(a.severity, 4))}
            </span>
            <b style={{ color: dirColor(a.direction) }}>{a.symbol}</b>
            <span className="alert-kind">{a.kind}</span>
            <span className="alert-note">{a.note}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
