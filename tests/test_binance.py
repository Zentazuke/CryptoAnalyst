"""BinanceSource: symbol/timeframe translation + parsing (offline + opt-in live)."""
from __future__ import annotations

import os

import pytest

from analyst.ingestion.binance import BinanceSource


def test_symbol_and_timeframe_translation():
    s = BinanceSource()
    assert s._sym("BTC_USDT") == "BTCUSDT"
    assert s.perp_for("ETH_USDT") == "ETHUSDT"
    assert s._interval("1D") == "1d"
    assert s._interval("1h") == "1h"
    with pytest.raises(Exception):
        s._interval("3w")


class StubBinance(BinanceSource):
    """Serves a synthetic klines response without hitting the network."""

    def _get(self, base, path, params):  # type: ignore[override]
        if path == "/api/v3/klines":
            start = 1_700_000_000_000
            step = 3_600_000
            return [
                [start + i * step, "100", "101", "99", str(100 + i), "5.0",
                 start + i * step + step - 1, "0", 10, "0", "0", "0"]
                for i in range(3)
            ]
        raise AssertionError(f"unexpected path {path}")


def test_parse_klines_into_candles():
    candles, raw = StubBinance().fetch_ohlcv("BTC_USDT", "1h", count=3)
    assert len(candles) == 3
    c = candles[-1]
    assert c.symbol == "BTC_USDT" and c.timeframe == "1h" and c.source == "binance"
    assert c.open == 100.0 and c.close == 102.0 and c.volume == 5.0
    assert [x.ts for x in candles] == sorted(x.ts for x in candles)


pytestmark_live = pytest.mark.skipif(
    os.environ.get("ANALYST_LIVE") != "1", reason="set ANALYST_LIVE=1 for live Binance test"
)


@pytestmark_live
def test_live_binance_klines_and_funding():
    with BinanceSource() as s:
        candles, _ = s.fetch_ohlcv("BTC_USDT", "1h", count=10)
        assert len(candles) == 10 and candles[-1].high >= candles[-1].low > 0
        funding, _ = s.fetch_funding_history("BTCUSDT", total=5)
        assert funding and "v" in funding[0]
