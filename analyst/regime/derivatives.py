"""Derivatives-derived regime features (funding rate).

Funding is positioning information, orthogonal to price-only TA: persistently
positive funding = crowded longs, negative = crowded shorts, and extremes often
precede squeezes. We align the hourly funding series to candle bars *causally*
(each bar takes the most recent funding observed at or before its timestamp) and
derive level, rolling percentile rank (extremeness), and slope (trend).
"""
from __future__ import annotations

import bisect
from typing import Any

import numpy as np

from analyst.regime.features import _rolling_pctl_rank, _slope

FUNDING_DEFAULTS = {"funding_rank_window": 168, "funding_slope_k": 24}


def _candle_ts(candles: list[Any]) -> list[int]:
    return [c["ts"] if isinstance(c, dict) else c.ts for c in candles]


def align_funding(candle_ts: list[int], funding_rows: list[dict]) -> np.ndarray:
    """Most-recent funding value at or before each candle ts (causal forward-fill)."""
    out = np.full(len(candle_ts), np.nan)
    if not funding_rows:
        return out
    f_ts = [r["t"] for r in funding_rows]
    f_v = [r["v"] for r in funding_rows]
    for i, ts in enumerate(candle_ts):
        j = bisect.bisect_right(f_ts, ts) - 1
        if j >= 0:
            out[i] = f_v[j]
    return out


def funding_features(
    candles: list[Any], funding_rows: list[dict], params: dict | None = None
) -> dict[str, np.ndarray]:
    """Return causal funding features aligned to candles."""
    p = {**FUNDING_DEFAULTS, **(params or {})}
    aligned = align_funding(_candle_ts(candles), funding_rows)
    return {
        "funding_rate": aligned,
        "funding_rank": _rolling_pctl_rank(aligned, p["funding_rank_window"]),
        "funding_chg": _slope(aligned, p["funding_slope_k"]),
    }
