"""End-to-end ingest pipeline with an offline fake source (no network)."""
from __future__ import annotations

from analyst.ingest import ingest_symbol
from analyst.models import Candle
from analyst.storage import Store

HOUR_MS = 3_600_000
START = 1_700_000_000_000


class FakeSource:
    """A DataSource that returns a fixed series with one deliberate gap."""

    name = "fake"

    def fetch_ohlcv(self, symbol, timeframe, count=300):
        idxs = [0, 1, 2, 4, 5]  # index 3 missing -> a gap
        candles = [
            Candle(
                symbol=symbol, timeframe=timeframe, ts=START + i * HOUR_MS,
                open=100.0, high=101.0, low=99.0, close=100.0 + i, volume=1.0,
                source=self.name, ingest_ts=START,
            )
            for i in idxs
        ]
        raw = {"code": 0, "result": {"instrument_name": symbol, "data": "..."}}
        return candles, raw


def test_pipeline_archives_stores_and_flags_gap(tmp_path):
    db = tmp_path / "t.duckdb"
    raw_dir = tmp_path / "raw"
    with Store(db) as store:
        result, gap = ingest_symbol(
            "BTC_USDT", "1h", 300, store, FakeSource(), raw_dir=raw_dir
        )

        # stored
        assert result.rows == 5
        assert store.get_candles("BTC_USDT", "1h")[0]["close"] == 100.0

        # raw archived to disk
        archived = list(raw_dir.glob("*.json"))
        assert len(archived) == 1

        # gap detected and recorded in data_quality
        assert gap.has_gaps
        assert gap.missing == [START + 3 * HOUR_MS]
        checks = store.quality("BTC_USDT")
        assert checks[0]["check_name"] == "gap_check"
        assert checks[0]["status"] == "fail"
