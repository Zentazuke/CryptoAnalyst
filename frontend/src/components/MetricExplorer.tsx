import { useEffect, useMemo, useState } from "react";
import { fetchMetricCatalog, fetchMetricSeries } from "../api";
import type { MetricCatalogEntry, MetricSeriesPoint } from "../api";

/** P3.2 — metric explorer over everything MetricHistory records.
 *
 *  Catalog of stored series (options / derivatives / stableflow / sentiment /
 *  on-chain) for the active symbol plus the GLOBAL stableflow bucket, with a
 *  dependency-free SVG line chart. Explicitly labeled UNCALIBRATED until the
 *  harness cards a series — this is a window into the raw evidence store, not
 *  a signal board. */

const W = 640;
const H = 160;
const PAD = 6;

function Chart({ pts }: { pts: MetricSeriesPoint[] }) {
  if (pts.length < 2) {
    return <p className="muted-txt">need at least 2 observations to draw — check back later.</p>;
  }
  const vals = pts.map((p) => p.value);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const t0 = pts[0].ts;
  const t1 = pts[pts.length - 1].ts;
  const tspan = t1 - t0 || 1;
  const path = pts
    .map((p) => {
      const x = PAD + ((p.ts - t0) / tspan) * (W - 2 * PAD);
      const y = H - PAD - ((p.value - lo) / span) * (H - 2 * PAD);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const fmt = (v: number) =>
    Math.abs(v) >= 1e9 ? `${(v / 1e9).toFixed(1)}B` :
    Math.abs(v) >= 1e6 ? `${(v / 1e6).toFixed(1)}M` :
    Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(3);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
        <polyline points={path} fill="none" stroke="#4f8cc9" strokeWidth={1.5} />
      </svg>
      <div className="muted-txt" style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
        <span>{new Date(t0).toISOString().slice(0, 16).replace("T", " ")}</span>
        <span>
          min {fmt(lo)} · max {fmt(hi)} · last <b>{fmt(vals[vals.length - 1])}</b>
        </span>
        <span>{new Date(t1).toISOString().slice(0, 16).replace("T", " ")}</span>
      </div>
    </div>
  );
}

export function MetricExplorer({ symbol }: { symbol: string }) {
  const [catalog, setCatalog] = useState<MetricCatalogEntry[]>([]);
  const [selected, setSelected] = useState<string>("");   // "layer|symbol|metric"
  const [series, setSeries] = useState<MetricSeriesPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    Promise.all([fetchMetricCatalog(symbol), fetchMetricCatalog("GLOBAL")]).then(
      ([own, global]) => {
        if (!alive) return;
        const cat = [...own, ...global];
        setCatalog(cat);
        if (cat.length && !cat.some((c) => `${c.layer}|${c.symbol}|${c.metric}` === selected)) {
          const first = cat[0];
          setSelected(`${first.layer}|${first.symbol}|${first.metric}`);
        }
      },
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  useEffect(() => {
    if (!selected) return;
    const [layer, sym, metric] = selected.split("|");
    let alive = true;
    setLoading(true);
    fetchMetricSeries(layer, sym, metric)
      .then((s) => alive && setSeries(s))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [selected]);

  const byLayer = useMemo(() => {
    const g: Record<string, MetricCatalogEntry[]> = {};
    for (const c of catalog) (g[c.layer] ??= []).push(c);
    return g;
  }, [catalog]);

  const current = catalog.find((c) => `${c.layer}|${c.symbol}|${c.metric}` === selected);

  return (
    <div className="card">
      <div className="card-title">Metric explorer · raw evidence store</div>
      {catalog.length === 0 ? (
        <p className="muted-txt">
          no persisted metrics yet for {symbol} — the scheduler records options / derivatives /
          stableflow / sentiment / on-chain history while the API runs (server does this 24/7).
        </p>
      ) : (
        <>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            style={{ maxWidth: "100%", marginBottom: 8 }}
          >
            {Object.entries(byLayer).map(([layer, entries]) => (
              <optgroup key={layer} label={layer}>
                {entries.map((c) => {
                  const key = `${c.layer}|${c.symbol}|${c.metric}`;
                  return (
                    <option key={key} value={key}>
                      {c.metric}
                      {c.symbol === "GLOBAL" ? " (global)" : ""} · n={c.n}
                    </option>
                  );
                })}
              </optgroup>
            ))}
          </select>
          {loading ? <p className="muted-txt">loading series…</p> : <Chart pts={series} />}
          {current && (
            <p className="footnote" style={{ marginTop: 6 }}>
              {current.layer}/{current.metric} · {current.n} observations ·{" "}
              <b>UNCALIBRATED</b> until /metric-calibration cards it on mature history — until
              then this is context to look at, never a signal to act on.
            </p>
          )}
        </>
      )}
    </div>
  );
}
