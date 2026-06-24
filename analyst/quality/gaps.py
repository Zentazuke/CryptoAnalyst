"""Gap detection.

A trustworthy time series must be honest about what is missing. Given a set of
candles and their timeframe, we reconstruct the *expected* grid of open-times
between the first and last observed bar and report any absent slots. We never
silently interpolate — missing data is surfaced, not hidden.
"""
from __future__ import annotations

from collections.abc import Iterable

from analyst.config import INTERVAL_SECONDS
from analyst.models import Candle, GapReport


def detect_gaps(candles: Iterable[Candle], timeframe: str) -> GapReport:
    """Detect missing bars in a candle series.

    Returns a :class:`GapReport`. With fewer than two candles there is nothing
    to compare, so the report is trivially gap-free.
    """
    if timeframe not in INTERVAL_SECONDS:
        raise ValueError(f"unknown timeframe {timeframe!r}")

    # Materialise once: the input may be a generator we need to traverse twice.
    candle_list = list(candles)
    step_ms = INTERVAL_SECONDS[timeframe] * 1000
    symbol = candle_list[0].symbol if candle_list else ""
    ts_sorted = sorted({c.ts for c in candle_list})

    if len(ts_sorted) < 2:
        return GapReport(
            symbol=symbol,
            timeframe=timeframe,
            expected=len(ts_sorted),
            present=len(ts_sorted),
            missing=[],
        )

    first, last = ts_sorted[0], ts_sorted[-1]
    expected_ts = list(range(first, last + 1, step_ms))
    present = set(ts_sorted)
    missing = [t for t in expected_ts if t not in present]

    return GapReport(
        symbol=symbol,
        timeframe=timeframe,
        expected=len(expected_ts),
        present=len(present),
        missing=missing,
    )
