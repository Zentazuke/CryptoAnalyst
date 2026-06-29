"""Measured calibration of the crowd-contrarian (funding-crowding) signal.

When funding sits in the top of its recent range, the crowd is paying to be
long (crowded longs) -> the contrarian expectation is a *lower* price ahead;
bottom of range = crowded shorts -> contrarian expects *higher*. This backtests
whether that actually held on the analyst's own deep funding history, reporting
hit-rate vs base rate and lift — the same honesty as the regime calibration.

Causal: the crowd label at bar i uses only funding observed up to i; only the
scoring looks forward.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from analyst import stats
from analyst.regime.derivatives import align_funding
from analyst.regime.features import _rolling_pctl_rank


def calibrate_funding_contrarian(
    candles: list[Any], funding_rows: list[dict], horizon: int = 24,
    window: int = 200, hi: float = 0.8, lo: float = 0.2,
) -> dict | None:
    """Backtest the funding-crowding contrarian signal. None if too few samples."""
    if not funding_rows or len(candles) < window + horizon:
        return None

    ts = [c["ts"] if isinstance(c, dict) else c.ts for c in candles]
    close = np.array([c["close"] if isinstance(c, dict) else c.close for c in candles], float)
    funding = align_funding(ts, funding_rows)
    rank = _rolling_pctl_rank(funding, window)  # causal trailing percentile of funding

    n = len(close)
    long_c = short_c = hits = 0
    base_down = base_total = 0
    for i in range(n - horizon):
        if not np.isfinite(close[i]) or close[i] <= 0:
            continue
        fwd = close[i + horizon] / close[i] - 1.0
        base_total += 1
        if fwd < 0:
            base_down += 1
        r = rank[i]
        if not np.isfinite(r):
            continue
        if r >= hi:            # crowded long -> contrarian expects down
            long_c += 1
            if fwd < 0:
                hits += 1
        elif r <= lo:          # crowded short -> contrarian expects up
            short_c += 1
            if fwd > 0:
                hits += 1

    crowd_n = long_c + short_c
    if crowd_n == 0 or base_total == 0:
        return None

    p_down = base_down / base_total
    hit_rate = hits / crowd_n
    # base = chance of "moved against the crowd" given the side mix
    base_rate = (long_c * p_down + short_c * (1.0 - p_down)) / crowd_n
    lift = hit_rate / base_rate if base_rate > 0 else None
    span_days = (ts[-1] - ts[0]) / 86_400_000.0

    ev = stats.evidence(hits, crowd_n, base_rate)
    return {
        "horizon": horizon,
        "count": crowd_n,
        "hit_rate": round(hit_rate, 4),
        "base_rate": round(base_rate, 4),
        "lift": round(lift, 3) if lift is not None else None,
        "span_days": round(span_days, 1),
        "ci_low": ev["ci_low"],
        "ci_high": ev["ci_high"],
        "significant": ev["significant"],
        "verdict": ev["verdict"],
    }
