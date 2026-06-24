"""Storage: idempotent upserts + provenance round-trip (A0 DoD)."""
from __future__ import annotations

from analyst.models import Candle, IngestResult
from analyst.storage import Store

HOUR_MS = 3_600_000
START = 1_700_000_000_000


def _candle(i: int, *, source: str = "crypto.com", ingest_ts: int = START, close: float = 100.0) -> Candle:
    return Candle(
        symbol="BTC_USDT", timeframe="1h", ts=START + i * HOUR_MS,
        open=100.0, high=101.0, low=99.0, close=close, volume=1.0,
        source=source, ingest_ts=ingest_ts,
    )


def test_upsert_is_idempotent(tmp_path):
    db = tmp_path / "t.duckdb"
    with Store(db) as store:
        candles = [_candle(i) for i in range(5)]
        store.upsert_candles(candles)
        store.upsert_candles(candles)  # re-ingest same bars
        rows = store.get_candles("BTC_USDT", "1h")
        assert len(rows) == 5  # no duplicates


def test_upsert_updates_in_place(tmp_path):
    db = tmp_path / "t.duckdb"
    with Store(db) as store:
        store.upsert_candles([_candle(0, close=100.0, ingest_ts=START)])
        store.upsert_candles([_candle(0, close=123.45, ingest_ts=START + 999)])
        rows = store.get_candles("BTC_USDT", "1h")
        assert len(rows) == 1
        assert rows[0]["close"] == 123.45
        assert rows[0]["ingest_ts"] == START + 999


def test_provenance_reports_source_and_ingest_ts(tmp_path):
    db = tmp_path / "t.duckdb"
    with Store(db) as store:
        store.upsert_candles([_candle(i) for i in range(3)])
        store.log_ingest(
            IngestResult(
                source="crypto.com", symbol="BTC_USDT", timeframe="1h",
                fetched_ts=START + 1, rows=3, raw_path="data/raw/x.json",
            )
        )
        prov = store.provenance("BTC_USDT")

    assert prov["symbol"] == "BTC_USDT"
    assert len(prov["series"]) == 1
    series = prov["series"][0]
    assert series["source"] == "crypto.com"
    assert series["candles"] == 3
    assert series["last_ingest_ts"] == START
    assert prov["recent_ingests"][0]["raw_path"] == "data/raw/x.json"
