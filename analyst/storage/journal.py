"""Live alert journal — records fired alerts so they accrue a real track record.

Kept in its own DuckDB file (the API holds the market DB read-only, so writing
there would fight the lock). De-duplicates by symbol+kind+timeframe within a
window, and is thread-safe for concurrent API requests.
"""
from __future__ import annotations

import threading

import duckdb

from analyst.config import DATA_DIR
from analyst.utils import now_ms

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_journal (
    fired_ts       BIGINT,
    symbol         VARCHAR,
    kind           VARCHAR,
    direction      VARCHAR,
    severity       INTEGER,
    timeframe      VARCHAR,
    price_at_fire  DOUBLE
);
"""


class AlertJournal:
    def __init__(self, path: str | None = None) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = str(path or (DATA_DIR / "alert_journal.duckdb"))
        self._lock = threading.Lock()
        self.conn = duckdb.connect(self.path)
        self.conn.execute(_SCHEMA)

    def record(self, alerts: list[dict], timeframe: str, dedup_hours: float = 6.0) -> int:
        now = now_ms()
        cutoff = now - int(dedup_hours * 3_600_000)
        written = 0
        with self._lock:
            for a in alerts:
                if a.get("price") is None:
                    continue
                dup = self.conn.execute(
                    "SELECT 1 FROM alert_journal WHERE symbol=? AND kind=? AND timeframe=? AND fired_ts>=? LIMIT 1",
                    [a["symbol"], a["kind"], timeframe, cutoff],
                ).fetchone()
                if dup:
                    continue
                self.conn.execute(
                    "INSERT INTO alert_journal VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [now, a["symbol"], a["kind"], a["direction"], a["severity"], timeframe, a["price"]],
                )
                written += 1
        return written

    def recent(self, limit: int = 100) -> list[dict]:
        with self._lock:
            cur = self.conn.execute(
                "SELECT fired_ts, symbol, kind, direction, severity, timeframe, price_at_fire "
                "FROM alert_journal ORDER BY fired_ts DESC LIMIT ?",
                [limit],
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
