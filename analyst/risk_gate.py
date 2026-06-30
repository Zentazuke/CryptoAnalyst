"""Analyst risk-state gate for vol selling.

The variance premium is real but its left tail (crash months) is what kills naive
short-vol. This is where the analyst earns its keep: not by generating the edge,
but by standing aside when conditions are dangerous. The gate answers, per day
and strictly causally, "is it safe to sell vol right now?".

Risk-off (stand aside) when any of:
  * vol is accelerating — trailing short-window realized vol >> trailing long-
    window (a vol event may be underway; vol clusters, so this predicts more),
  * price is in a drawdown from its recent high (crashes cluster in selloffs),
  * the regime classifier reads FLASH_RISK (a volatility shock).

Each component is configurable so the backtest can test which actually helps,
rather than assuming.
"""
from __future__ import annotations

import math

import numpy as np

from analyst.regime import classify_series
from analyst.regime import classifier as C


def _closes(candles) -> np.ndarray:
    return np.array([(c["close"] if isinstance(c, dict) else c.close) for c in candles], float)


def _trailing_vol(rets: np.ndarray, t: int, window: int) -> float:
    """Annualized realized vol (%) over the `window` returns ending at day t."""
    seg = rets[max(0, t - window): t]
    if len(seg) < max(2, window // 2):
        return float("nan")
    return float(np.std(seg, ddof=0) * math.sqrt(365) * 100.0)


def vol_sell_gate(
    candles, *, use_vol_accel: bool = True, accel: float = 1.3, short: int = 5, long: int = 30,
    use_drawdown: bool = True, dd_lookback: int = 20, dd_thresh: float = 0.12,
    use_regime: bool = True,
) -> np.ndarray:
    """Per-day boolean: True = safe to sell vol, False = stand aside. Causal."""
    cl = _closes(candles)
    n = len(cl)
    rets = np.diff(np.log(cl))  # rets[j] is the return into day j+1
    labels = np.array([r.label for r in classify_series(candles)], dtype=object) if use_regime else None

    ok = np.ones(n, dtype=bool)
    for t in range(n):
        risk_off = False
        if use_vol_accel:
            vs, vl = _trailing_vol(rets, t, short), _trailing_vol(rets, t, long)
            if np.isfinite(vs) and np.isfinite(vl) and vl > 0 and vs > accel * vl:
                risk_off = True
        if use_drawdown and not risk_off:
            hi = cl[max(0, t - dd_lookback + 1): t + 1].max()
            if hi > 0 and cl[t] < (1.0 - dd_thresh) * hi:
                risk_off = True
        if use_regime and not risk_off and labels is not None:
            if labels[t] == C.FLASH_RISK:
                risk_off = True
        ok[t] = not risk_off
    return ok
