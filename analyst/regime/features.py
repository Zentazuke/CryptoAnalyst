"""Causal feature set for regime classification.

Each feature at index ``i`` uses only data at indices ``<= i``. Rolling
statistics use either the trailing window inclusive of ``i`` (volatility level,
percentile rank) or the strictly-prior window (Donchian extremes, volume
baseline) so a current-bar event is measured against its past, never its future.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from analyst.features import indicators as ind

REGIME_DEFAULTS: dict[str, Any] = {
    "adx_period": 14,
    "ema_fast": 20,
    "ema_slow": 50,
    "slope_k": 10,        # bars over which EMA slope is measured
    "bb_period": 20,
    "bandwidth_chg_k": 10,
    "atr_period": 14,
    "atr_pctl_window": 100,  # window for ATR% percentile rank (vol regime)
    "donchian_n": 20,
    "vol_window": 20,
}


def _ohlcv(candles: list[Any]) -> dict[str, np.ndarray]:
    def g(c: Any, k: str) -> float:
        return c[k] if isinstance(c, dict) else getattr(c, k)

    keys = ("open", "high", "low", "close", "volume")
    return {k: np.array([g(c, k) for c in candles], dtype=float) for k in keys}


def _slope(series: np.ndarray, k: int) -> np.ndarray:
    out = np.full(series.shape, np.nan)
    for i in range(k, len(series)):
        a, b = series[i], series[i - k]
        if np.isfinite(a) and np.isfinite(b) and b != 0:
            out[i] = (a - b) / abs(b)
    return out


def _prior_extreme(series: np.ndarray, n: int, kind: str) -> np.ndarray:
    """Max/min over the strictly-prior ``n`` bars (excludes current bar)."""
    out = np.full(series.shape, np.nan)
    for i in range(n, len(series)):
        w = series[i - n:i]
        out[i] = w.max() if kind == "max" else w.min()
    return out


def _rolling_pctl_rank(series: np.ndarray, window: int) -> np.ndarray:
    """Percentile rank of the current value within the trailing window [0,1]."""
    out = np.full(series.shape, np.nan)
    for i in range(len(series)):
        cur = series[i]
        if not np.isfinite(cur):
            continue
        w = series[max(0, i - window + 1):i + 1]
        valid = w[np.isfinite(w)]
        if len(valid) >= 5:
            out[i] = float((valid <= cur).sum()) / len(valid)
    return out


def _rolling_z_prior(series: np.ndarray, window: int) -> np.ndarray:
    """Z-score of current value vs the strictly-prior window's mean/std."""
    out = np.full(series.shape, np.nan)
    for i in range(window, len(series)):
        w = series[i - window:i]
        m, s = w.mean(), w.std(ddof=0)
        out[i] = (series[i] - m) / s if s > 0 else 0.0
    return out


def compute_regime_features(
    candles: list[Any], params: dict | None = None
) -> dict[str, np.ndarray]:
    """Compute all regime features as aligned arrays (NaN during warmup)."""
    p = {**REGIME_DEFAULTS, **(params or {})}
    a = _ohlcv(candles)
    close, high, low, vol = a["close"], a["high"], a["low"], a["volume"]

    adx, plus_di, minus_di = ind.adx(high, low, close, p["adx_period"])
    ema_slow = ind.ema(close, p["ema_slow"])
    atr = ind.atr(high, low, close, p["atr_period"])
    with np.errstate(divide="ignore", invalid="ignore"):
        atr_pct = atr / close
    _, _, _, bandwidth = ind.bollinger(close, p["bb_period"])

    # one-bar return expressed in ATR units (shock magnitude)
    ret_atr = np.full(close.shape, np.nan)
    for i in range(1, len(close)):
        if np.isfinite(atr[i]) and atr[i] > 0:
            ret_atr[i] = (close[i] - close[i - 1]) / atr[i]

    bandwidth_chg = _slope(bandwidth, p["bandwidth_chg_k"])

    return {
        "close": close,
        "adx": adx,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "ema_slope": _slope(ema_slow, p["slope_k"]),
        "bb_bandwidth": bandwidth,
        "bandwidth_chg": bandwidth_chg,
        "atr_pct": atr_pct,
        "atr_pct_rank": _rolling_pctl_rank(atr_pct, p["atr_pctl_window"]),
        "donchian_hi": _prior_extreme(high, p["donchian_n"], "max"),
        "donchian_lo": _prior_extreme(low, p["donchian_n"], "min"),
        "ret_atr": ret_atr,
        "vol_z": _rolling_z_prior(vol, p["vol_window"]),
    }
