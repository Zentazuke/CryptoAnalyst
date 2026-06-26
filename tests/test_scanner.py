"""Market scanner: ranking, breadth aggregates, setups (offline fake source)."""
from __future__ import annotations

import numpy as np

from analyst.models import Candle
from analyst.scanner import scan_symbols

HOUR = 3_600_000
START = 1_700_000_000_000


class FakeScanSource:
    """AAA = strong uptrend, BBB = downtrend; funding extremes on each."""

    def fetch_all_funding(self):
        return {"AAAUSDT": 0.0005, "BBBUSDT": -0.0005}

    def fetch_ohlcv(self, sym, timeframe, count):
        n = 150
        if sym == "AAAUSDT":
            close = 100.0 * (1.0 + np.linspace(0, 0.5, n))
        else:
            close = 100.0 * (1.0 - np.linspace(0, 0.4, n))
        candles = [
            Candle(symbol=sym, timeframe=timeframe, ts=START + i * HOUR,
                   open=float(close[i - 1] if i else close[0]),
                   high=float(close[i]) * 1.002, low=float(close[i]) * 0.998,
                   close=float(close[i]), volume=1.0, source="fake", ingest_ts=START)
            for i in range(n)
        ]
        return candles, {}


def test_scan_ranks_by_momentum_and_summarises():
    res = scan_symbols(FakeScanSource(), ["AAAUSDT", "BBBUSDT"], timeframe="4h")
    assert res["count"] == 2
    # AAA (uptrend) ranks first by relative strength
    assert res["rows"][0]["symbol"] == "AAA" and res["rows"][0]["rank"] == 1
    assert res["rows"][0]["regime"] == "trend_up"
    assert res["rows"][-1]["symbol"] == "BBB"
    # breadth aggregates
    agg = res["aggregates"]
    assert 0.0 <= agg["pct_uptrend"] <= 1.0
    assert agg["breadth"] in ("risk-on", "risk-off", "mixed")


def test_scan_surfaces_funding_setups():
    res = scan_symbols(FakeScanSource(), ["AAAUSDT", "BBBUSDT"], timeframe="4h")
    kinds = {(s["kind"], s["symbol"]) for s in res["setups"]}
    assert ("crowded-long", "AAA") in kinds      # funding +0.05% -> contrarian-bearish
    assert ("crowded-short", "BBB") in kinds      # funding -0.05% -> contrarian-bullish


def test_scan_skips_short_series():
    class ShortSource(FakeScanSource):
        def fetch_ohlcv(self, sym, timeframe, count):
            c, raw = super().fetch_ohlcv(sym, timeframe, count)
            return c[:10], raw

    res = scan_symbols(ShortSource(), ["AAAUSDT"], timeframe="4h")
    assert res["count"] == 0
