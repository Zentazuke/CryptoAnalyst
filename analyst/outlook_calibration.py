"""Does the Note's *combined* call beat its parts?

We can reconstruct three of the outlook's directional components causally from
history: the technical regime, the higher-timeframe regime, and the funding-
crowd contrarian read. (The live news-sentiment component has no history, so it
is honestly excluded here.) For each, and for their agreement, we measure the
vol-scaled forward hit-rate vs base rate and lift — answering whether confluence
actually adds value or just sounds good.
"""
from __future__ import annotations

import bisect
import math
from typing import Any

import numpy as np

from analyst import stats
from analyst.features import indicators as ind
from analyst.regime import classify_series
from analyst.regime import classifier as C
from analyst.regime.derivatives import align_funding
from analyst.regime.features import _rolling_pctl_rank


def _regime_bias(label: str) -> int:
    return 1 if label == C.TREND_UP else -1 if label == C.TREND_DOWN else 0


def _ohlc_ts(candles: list[Any]):
    def col(k):
        return np.array([c[k] if isinstance(c, dict) else getattr(c, k) for c in candles], float)
    ts = [c["ts"] if isinstance(c, dict) else c.ts for c in candles]
    return ts, col("high"), col("low"), col("close")


def calibrate_combined(
    candles: list[Any], funding_rows: list[dict] | None = None,
    htf_candles: list[Any] | None = None, horizon: int = 24, k: float = 1.0, window: int = 200,
) -> dict | None:
    ts, high, low, close = _ohlc_ts(candles)
    n = len(close)
    if n < window + horizon + 10:
        return None
    atr = ind.atr(high, low, close, 14)

    reg_bias = np.array([_regime_bias(r.label) for r in classify_series(candles)])

    crowd_bias = np.zeros(n)
    if funding_rows:
        rank = _rolling_pctl_rank(align_funding(ts, funding_rows), window)
        for i in range(n):
            if np.isfinite(rank[i]):
                crowd_bias[i] = -1 if rank[i] >= 0.8 else 1 if rank[i] <= 0.2 else 0

    htf_bias = np.zeros(n)
    if htf_candles and len(htf_candles) >= 60:
        h_ts = [c["ts"] if isinstance(c, dict) else c.ts for c in htf_candles]
        h_lab = [_regime_bias(r.label) for r in classify_series(htf_candles)]
        for i, t in enumerate(ts):
            j = bisect.bisect_right(h_ts, t) - 1
            if j >= 0:
                htf_bias[i] = h_lab[j]

    sqrt_h = math.sqrt(horizon)

    def evaluate(bias: np.ndarray) -> dict | None:
        long_c = short_c = hits = base_up = base_down = base_total = 0
        for i in range(n - horizon):
            if not (np.isfinite(close[i]) and np.isfinite(atr[i]) and close[i] > 0 and atr[i] > 0):
                continue
            thr = k * (atr[i] / close[i]) * sqrt_h
            r = close[i + horizon] / close[i] - 1.0
            base_total += 1
            if r > thr:
                base_up += 1
            elif r < -thr:
                base_down += 1
            b = bias[i]
            if b > 0:
                long_c += 1
                hits += r > thr
            elif b < 0:
                short_c += 1
                hits += r < -thr
        cn = long_c + short_c
        if cn == 0 or base_total == 0:
            return None
        hit_rate = hits / cn
        base_rate = (long_c * base_up / base_total + short_c * base_down / base_total) / cn
        lift = hit_rate / base_rate if base_rate > 0 else None
        ev = stats.evidence(int(hits), cn, base_rate)
        return {"count": cn, "hit_rate": round(hit_rate, 4),
                "base_rate": round(base_rate, 4), "lift": round(lift, 3) if lift else None,
                "ci_low": ev["ci_low"], "ci_high": ev["ci_high"],
                "significant": ev["significant"], "verdict": ev["verdict"]}

    comps = [reg_bias, crowd_bias] + ([htf_bias] if htf_candles is not None else [])
    agree2 = np.where((reg_bias != 0) & (reg_bias == crowd_bias), reg_bias, 0)
    all_agree = np.zeros(n)
    for i in range(n):
        vals = [c[i] for c in comps]
        if all(v > 0 for v in vals):
            all_agree[i] = 1
        elif all(v < 0 for v in vals):
            all_agree[i] = -1

    return {
        "horizon": horizon,
        "per_signal": {
            "regime": evaluate(reg_bias),
            "crowd": evaluate(crowd_bias) if funding_rows else None,
            "htf": evaluate(htf_bias) if htf_candles is not None else None,
            "regime+crowd_agree": evaluate(agree2),
            "all_agree": evaluate(all_agree),
        },
    }
