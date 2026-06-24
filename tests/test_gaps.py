"""Gap detection must flag a deliberately-dropped candle (A0 DoD)."""
from __future__ import annotations

from analyst.models import Candle
from analyst.quality import detect_gaps

HOUR_MS = 3_600_000


def _series(n: int, start: int = 1_700_000_000_000) -> list[Candle]:
    return [
        Candle(
            symbol="BTC_USDT",
            timeframe="1h",
            ts=start + i * HOUR_MS,
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1.0,
            source="test",
            ingest_ts=start,
        )
        for i in range(n)
    ]


def test_contiguous_series_has_no_gaps():
    report = detect_gaps(_series(10), "1h")
    assert not report.has_gaps
    assert report.expected == report.present == 10


def test_dropped_candle_is_flagged():
    candles = _series(10)
    dropped = candles[5]
    remaining = candles[:5] + candles[6:]

    report = detect_gaps(remaining, "1h")

    assert report.has_gaps
    assert report.present == 9
    assert report.expected == 10
    assert report.missing == [dropped.ts]


def test_multiple_gaps_listed_in_order():
    candles = _series(12)
    remaining = [c for i, c in enumerate(candles) if i not in (3, 4, 8)]
    report = detect_gaps(remaining, "1h")
    assert report.missing == [candles[3].ts, candles[4].ts, candles[8].ts]


def test_single_candle_is_trivially_gap_free():
    report = detect_gaps(_series(1), "1h")
    assert not report.has_gaps
