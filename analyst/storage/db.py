"""DuckDB-backed store.

Holds OHLCV plus two trust tables: ``ingest_log`` (provenance of every fetch
batch) and ``data_quality`` (results of checks such as gap detection).

Candle writes are idempotent: re-ingesting the same bar updates it in place via
``ON CONFLICT``, so the store can be safely re-run without creating duplicates.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from analyst.models import Candle, GapReport, IngestResult
from analyst.utils import now_ms

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol     VARCHAR,
    timeframe  VARCHAR,
    ts         BIGINT,
    open       DOUBLE,
    high       DOUBLE,
    low        DOUBLE,
    close      DOUBLE,
    volume     DOUBLE,
    source     VARCHAR,
    ingest_ts  BIGINT,
    PRIMARY KEY (symbol, timeframe, ts)
);

CREATE SEQUENCE IF NOT EXISTS seq_ingest_log START 1;
CREATE TABLE IF NOT EXISTS ingest_log (
    id          BIGINT DEFAULT nextval('seq_ingest_log'),
    source      VARCHAR,
    symbol      VARCHAR,
    timeframe   VARCHAR,
    fetched_ts  BIGINT,
    rows        INTEGER,
    raw_path    VARCHAR,
    status      VARCHAR
);

CREATE TABLE IF NOT EXISTS data_quality (
    check_name  VARCHAR,
    source      VARCHAR,
    symbol      VARCHAR,
    timeframe   VARCHAR,
    ts_from     BIGINT,
    ts_to       BIGINT,
    status      VARCHAR,
    detail      VARCHAR,
    created_ts  BIGINT
);
"""


class Store:
    """Thin DuckDB wrapper. Use one instance per process for writes."""

    def __init__(self, db_path: str | Path, read_only: bool = False) -> None:
        self.db_path = str(db_path)
        if not read_only:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(self.db_path, read_only=read_only)
        if not read_only:
            self.conn.execute(_SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- writes -----------------------------------------------------------

    def upsert_candles(self, candles: list[Candle]) -> int:
        """Insert or update candles. Returns the number of rows written."""
        if not candles:
            return 0
        params = [
            (
                c.symbol, c.timeframe, c.ts,
                c.open, c.high, c.low, c.close, c.volume,
                c.source, c.ingest_ts,
            )
            for c in candles
        ]
        self.conn.executemany(
            """
            INSERT INTO ohlcv
                (symbol, timeframe, ts, open, high, low, close, volume, source, ingest_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol, timeframe, ts) DO UPDATE SET
                open      = EXCLUDED.open,
                high      = EXCLUDED.high,
                low       = EXCLUDED.low,
                close     = EXCLUDED.close,
                volume    = EXCLUDED.volume,
                source    = EXCLUDED.source,
                ingest_ts = EXCLUDED.ingest_ts
            """,
            params,
        )
        return len(params)

    def log_ingest(self, result: IngestResult) -> None:
        self.conn.execute(
            """
            INSERT INTO ingest_log (source, symbol, timeframe, fetched_ts, rows, raw_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                result.source, result.symbol, result.timeframe,
                result.fetched_ts, result.rows, result.raw_path, result.status,
            ],
        )

    def record_gap_check(self, source: str, report: GapReport) -> None:
        status = "fail" if report.has_gaps else "pass"
        detail = (
            f"{len(report.missing)} missing of {report.expected} expected"
            if report.has_gaps
            else f"{report.present} contiguous bars"
        )
        ts_from = report.missing[0] if report.missing else None
        ts_to = report.missing[-1] if report.missing else None
        self.conn.execute(
            """
            INSERT INTO data_quality
                (check_name, source, symbol, timeframe, ts_from, ts_to, status, detail, created_ts)
            VALUES ('gap_check', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [source, report.symbol, report.timeframe, ts_from, ts_to, status, detail, now_ms()],
        )

    # ---- reads ------------------------------------------------------------

    def get_candles(self, symbol: str, timeframe: str, limit: int | None = None) -> list[dict]:
        sql = (
            "SELECT symbol, timeframe, ts, open, high, low, close, volume, source, ingest_ts "
            "FROM ohlcv WHERE symbol = ? AND timeframe = ? ORDER BY ts"
        )
        params: list[object] = [symbol, timeframe]
        if limit is not None:
            sql += " DESC LIMIT ?"
            params.append(limit)
        cur = self.conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return rows[::-1] if limit is not None else rows

    def provenance(self, symbol: str) -> dict:
        """Per-(timeframe, source) provenance summary for a symbol."""
        cur = self.conn.execute(
            """
            SELECT timeframe, source,
                   COUNT(*)        AS candles,
                   MIN(ts)         AS first_ts,
                   MAX(ts)         AS last_ts,
                   MAX(ingest_ts)  AS last_ingest_ts
            FROM ohlcv
            WHERE symbol = ?
            GROUP BY timeframe, source
            ORDER BY timeframe, source
            """,
            [symbol],
        )
        cols = [d[0] for d in cur.description]
        series = [dict(zip(cols, r)) for r in cur.fetchall()]

        cur = self.conn.execute(
            """
            SELECT source, symbol, timeframe, fetched_ts, rows, raw_path, status
            FROM ingest_log WHERE symbol = ? ORDER BY fetched_ts DESC LIMIT 10
            """,
            [symbol],
        )
        cols = [d[0] for d in cur.description]
        recent_ingests = [dict(zip(cols, r)) for r in cur.fetchall()]

        return {"symbol": symbol, "series": series, "recent_ingests": recent_ingests}

    def quality(self, symbol: str, limit: int = 20) -> list[dict]:
        cur = self.conn.execute(
            """
            SELECT check_name, source, symbol, timeframe, ts_from, ts_to, status, detail, created_ts
            FROM data_quality WHERE symbol = ? ORDER BY created_ts DESC LIMIT ?
            """,
            [symbol, limit],
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
