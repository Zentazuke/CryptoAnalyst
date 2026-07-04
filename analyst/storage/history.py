"""Persistent metric history — the P1.1 foundation for calibrating the
sentiment and on-chain layers.

The upgrade plan's rule: without stored history there is no calibration, and
without calibration a metric is decoration. This store accrues timestamped
numeric snapshots of any layer in ONE long-format table, so the calibration
harness (P1.2) can score any series the same way it scores candle signals.

Own DuckDB file (like AlertJournal): the API holds the market DB read-only, so
writing there would fight the lock. Thread-safe; de-duplicates per metric by a
minimum time gap so an eager scheduler can't bloat the table.
"""
from __future__ import annotations

import math
import threading
from typing import Any

import duckdb

from analyst.config import DATA_DIR
from analyst.utils import now_ms

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metric_history (
    layer     VARCHAR,   -- 'sentiment' | 'onchain' | future layers
    symbol    VARCHAR,
    metric    VARCHAR,   -- dotted path from flatten_numeric, e.g. 'positioning.lsr'
    ts        BIGINT,    -- observation time (ms, UTC)
    value     DOUBLE,
    source    VARCHAR,
    ingest_ts BIGINT
);
"""


def flatten_numeric(obj: Any, prefix: str = "", max_depth: int = 4) -> dict[str, float]:
    """Flatten a nested dict to dotted-key -> float. Numbers kept, bools become
    1.0/0.0, strings/None/lists skipped (lists have no stable per-snapshot key).
    Only finite values survive — NaN/inf never reach the table."""
    out: dict[str, float] = {}
    if max_depth < 0 or not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, bool):
            out[key] = 1.0 if v else 0.0
        elif isinstance(v, (int, float)):
            f = float(v)
            if math.isfinite(f):
                out[key] = f
        elif isinstance(v, dict):
            out.update(flatten_numeric(v, key, max_depth - 1))
    return out


class MetricHistory:
    def __init__(self, path: str | None = None) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = str(path or (DATA_DIR / "metric_history.duckdb"))
        self._lock = threading.Lock()
        self.conn = duckdb.connect(self.path)
        self.conn.execute(_SCHEMA)

    def record(self, layer: str, symbol: str, values: dict[str, float], source: str,
               ts: int | None = None, min_gap_s: int = 0) -> int:
        """Insert one snapshot's numeric values. A metric already recorded within
        `min_gap_s` of `ts` is skipped (dedup), so cadence is bounded per metric."""
        ts = ts or now_ms()
        ingest = now_ms()
        clean = {k: float(v) for k, v in values.items()
                 if isinstance(v, (int, float)) and not isinstance(v, bool)
                 and math.isfinite(float(v))}
        if not clean:
            return 0
        written = 0
        with self._lock:
            last: dict[str, int] = {}
            if min_gap_s > 0:
                last = dict(self.conn.execute(
                    "SELECT metric, MAX(ts) FROM metric_history "
                    "WHERE layer=? AND symbol=? GROUP BY metric",
                    [layer, symbol]).fetchall())
            cutoff = ts - min_gap_s * 1000
            for metric, value in clean.items():
                if min_gap_s > 0 and last.get(metric) is not None and last[metric] > cutoff:
                    continue
                self.conn.execute(
                    "INSERT INTO metric_history VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [layer, symbol, metric, ts, value, source, ingest])
                written += 1
        return written

    def series(self, layer: str, symbol: str, metric: str, limit: int = 100_000) -> list[dict]:
        """Chronological [{ts, value}] for one metric."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT ts, value FROM metric_history "
                "WHERE layer=? AND symbol=? AND metric=? ORDER BY ts DESC LIMIT ?",
                [layer, symbol, metric, limit]).fetchall()
        return [{"ts": t, "value": v} for t, v in reversed(rows)]

    def catalog(self, layer: str | None = None) -> list[dict]:
        """What series exist, how deep, how fresh — the metric explorer's index."""
        q = ("SELECT layer, symbol, metric, COUNT(*) AS n, MIN(ts) AS first_ts, "
             "MAX(ts) AS last_ts FROM metric_history ")
        args: list = []
        if layer:
            q += "WHERE layer=? "
            args.append(layer)
        q += "GROUP BY layer, symbol, metric ORDER BY layer, symbol, metric"
        with self._lock:
            cur = self.conn.execute(q, args)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
