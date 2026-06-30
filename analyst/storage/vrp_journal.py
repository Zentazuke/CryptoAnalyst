"""Live VRP signal journal — forward-validates the volatility-risk-premium read.

Records the daily VRP read (implied DVOL, realized, premium, percentile, verdict)
so that, weeks later, we can check whether the *live* signal actually paid: did
"rich" entries precede lower realized vol (profitable short-vol) more than "cheap"
ones? This is the one validation backtests can't give — it needs real elapsed
time. Own DuckDB file (the market DB is held read-only by the API).
"""
from __future__ import annotations

import threading

import duckdb

from analyst.config import DATA_DIR
from analyst.utils import now_ms

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vrp_journal (
    ts             BIGINT,
    currency       VARCHAR,
    implied_vol    DOUBLE,
    realized_30d   DOUBLE,
    premium        DOUBLE,
    percentile     DOUBLE,
    verdict        VARCHAR
);
"""


class VrpJournal:
    def __init__(self, path: str | None = None) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = str(path or (DATA_DIR / "vrp_journal.duckdb"))
        self._lock = threading.Lock()
        self.conn = duckdb.connect(self.path)
        self.conn.execute(_SCHEMA)

    def record(self, read: dict, dedup_hours: float = 20.0) -> bool:
        """Journal one VRP read, de-duped per currency within the window (daily)."""
        cur = read.get("currency")
        if cur is None or read.get("premium_volpts") is None:
            return False
        now = now_ms()
        cutoff = now - int(dedup_hours * 3_600_000)
        with self._lock:
            dup = self.conn.execute(
                "SELECT 1 FROM vrp_journal WHERE currency=? AND ts>=? LIMIT 1", [cur, cutoff]
            ).fetchone()
            if dup:
                return False
            self.conn.execute(
                "INSERT INTO vrp_journal VALUES (?, ?, ?, ?, ?, ?, ?)",
                [now, cur, read["implied_vol_dvol"], read["realized_vol_30d"],
                 read["premium_volpts"], read["premium_percentile"], read["verdict"]],
            )
        return True

    def recent(self, limit: int = 200, currency: str | None = None) -> list[dict]:
        with self._lock:
            sql = ("SELECT ts, currency, implied_vol, realized_30d, premium, percentile, verdict "
                   "FROM vrp_journal")
            params: list = []
            if currency:
                sql += " WHERE currency=?"
                params.append(currency)
            sql += " ORDER BY ts DESC LIMIT ?"
            params.append(limit)
            cur = self.conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
