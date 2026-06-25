"""Calibration: backtest the classifier's own calls against realized outcomes.

For each historical bar we already labelled, we look ``horizon`` bars FORWARD
and check whether the label's expectation held. This is an *offline evaluation*
that is deliberately allowed to use future data — the classification itself
remains strictly causal; only the scoring looks ahead.

Expectations (forward return ``r`` and path range scaled by the bar's ATR%):
  trend_up      : r >  move_k * atr% * sqrt(H)
  trend_down    : r < -move_k * atr% * sqrt(H)
  breakout      : |r| >  move_k * atr% * sqrt(H)
  range         : |r| <= range_k * atr% * sqrt(H)        (stayed contained)
  low_vol_drift : path range <= range_k * atr% * sqrt(H) (stayed quiet)
  flash_risk    : path range >= move_k * atr% * sqrt(H)  (volatility followed)

Per label we report hit-rate, the unconditional base rate of that same
outcome, and the *lift* (hit-rate / base-rate). Lift > 1 means the label
carried information beyond chance.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from analyst.features import indicators as ind
from analyst.regime import classifier as C

CALIB_DEFAULTS = {"horizon": 12, "move_k": 1.0, "range_k": 0.5}


def _ohlc(candles: list[Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    def g(c, k):
        return c[k] if isinstance(c, dict) else getattr(c, k)

    high = np.array([g(c, "high") for c in candles], float)
    low = np.array([g(c, "low") for c in candles], float)
    close = np.array([g(c, "close") for c in candles], float)
    return high, low, close


def _outcome_matches(label: str, r: float, path_range: float, move_thr: float, range_thr: float) -> bool:
    if label == C.TREND_UP:
        return r > move_thr
    if label == C.TREND_DOWN:
        return r < -move_thr
    if label == C.BREAKOUT:
        return abs(r) > move_thr
    if label == C.RANGE:
        return abs(r) <= range_thr
    if label == C.LOW_VOL_DRIFT:
        return path_range <= range_thr
    if label == C.FLASH_RISK:
        return path_range >= move_thr
    return False


def calibrate(
    candles: list[Any],
    results: list[C.RegimeResult] | None = None,
    params: dict | None = None,
) -> dict:
    """Score regime calls against forward outcomes. Returns a per-label report."""
    p = {**CALIB_DEFAULTS, **(params or {})}
    horizon = int(p["horizon"])
    move_k, range_k = p["move_k"], p["range_k"]

    if results is None:
        results = C.classify_series(candles, params)

    high, low, close = _ohlc(candles)
    atr = ind.atr(high, low, close, 14)
    n = len(close)
    sqrt_h = math.sqrt(horizon)

    # tallies per label
    counts: dict[str, int] = {lab: 0 for lab in C.LABELS}
    hits: dict[str, int] = {lab: 0 for lab in C.LABELS}
    # unconditional outcome occurrences (for base rates), keyed by label semantics
    base_occ: dict[str, int] = {lab: 0 for lab in C.LABELS}
    base_total = 0

    for i in range(n - horizon):
        if not np.isfinite(close[i]) or not np.isfinite(atr[i]) or close[i] <= 0:
            continue
        atr_pct = atr[i] / close[i]
        move_thr = move_k * atr_pct * sqrt_h
        range_thr = range_k * atr_pct * sqrt_h

        seg = close[i:i + horizon + 1]
        r = close[i + horizon] / close[i] - 1.0
        path_range = (np.nanmax(seg) - np.nanmin(seg)) / close[i]

        # base rates: how often each expectation holds unconditionally
        base_total += 1
        for lab in (C.TREND_UP, C.TREND_DOWN, C.BREAKOUT, C.RANGE, C.LOW_VOL_DRIFT, C.FLASH_RISK):
            if _outcome_matches(lab, r, path_range, move_thr, range_thr):
                base_occ[lab] += 1

        label = results[i].label
        if label in (C.UNKNOWN,):
            continue
        counts[label] += 1
        if _outcome_matches(label, r, path_range, move_thr, range_thr):
            hits[label] += 1

    report: dict[str, Any] = {}
    for lab in C.LABELS:
        if lab == C.UNKNOWN:
            continue
        c = counts[lab]
        hit_rate = hits[lab] / c if c else None
        base_rate = base_occ[lab] / base_total if base_total else None
        lift = (hit_rate / base_rate) if (hit_rate is not None and base_rate) else None
        report[lab] = {
            "count": c,
            "hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
            "base_rate": round(base_rate, 4) if base_rate is not None else None,
            "lift": round(lift, 3) if lift is not None else None,
        }

    return {
        "horizon": horizon,
        "samples": base_total,
        "params": {"move_k": move_k, "range_k": range_k},
        "per_label": report,
    }
