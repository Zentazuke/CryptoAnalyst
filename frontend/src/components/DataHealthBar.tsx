import type { DataHealth } from "../types";

const STATUS: Record<string, { color: string; label: string }> = {
  ok: { color: "#3fb950", label: "All feeds live" },
  degraded: { color: "#d29922", label: "Collector degraded" },
  stale: { color: "#f85149", label: "Stale data — not live" },
};

const ago = (s: number | null) => {
  if (s == null) return "n/a";
  if (s < 90) return `${s}s ago`;
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  if (s < 172800) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
};

/** Slim liveness strip: rolled-up data-health + collector status, so degraded
 *  or stale feeds are loud rather than silently shown as current. */
export function DataHealthBar({ health }: { health: DataHealth | null }) {
  if (!health) return null;
  const s = STATUS[health.status] ?? STATUS.ok;
  const freshest = health.feeds.reduce<number | null>(
    (m, f) => (f.age_seconds == null ? m : m == null ? f.age_seconds : Math.min(m, f.age_seconds)),
    null,
  );
  const stale = health.feeds.filter((f) => f.stale);
  const sc = health.scheduler;

  return (
    <div className="health-bar" title={stale.length ? `Stale: ${stale.map((f) => `${f.symbol} ${f.timeframe}`).join(", ")}` : undefined}>
      <span className="health-dot" style={{ background: s.color, boxShadow: `0 0 0 3px ${s.color}22` }} />
      <span className="health-label" style={{ color: s.color }}>{s.label}</span>
      {freshest != null && health.status === "ok" && (
        <span className="health-meta">· freshest feed {ago(freshest)}</span>
      )}
      {stale.length > 0 && (
        <span className="health-meta">· {stale.length} feed{stale.length > 1 ? "s" : ""} stale</span>
      )}
      <span className="health-spacer" />
      {sc.enabled ? (
        <span className="health-meta">
          collector {sc.running ? "running" : "stopped"}
          {sc.errors > 0 && <span style={{ color: "#d29922" }}> · {sc.errors} error{sc.errors > 1 ? "s" : ""}</span>}
        </span>
      ) : (
        <span className="health-meta">collector off</span>
      )}
    </div>
  );
}
