"""Compute the standard indicator set from candles, with versioned provenance.

`compute_indicators` returns full aligned arrays (for charting / persistence);
`snapshot` returns the latest finite value of each indicator plus metadata. The
``INDICATOR_VERSION`` bumps whenever a formula changes, so stored values remain
reproducible and auditable.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from analyst.features import indicators as ind

INDICATOR_VERSION = "1.0"

# Default parameters for the standard set.
DEFAULTS: dict[str, Any] = {
    "sma": 20,
    "ema": 20,
    "rsi": 14,
    "macd": (12, 26, 9),
    "bollinger": (20, 2.0),
    "atr": 14,
    "adx": 14,
    "vwap": 20,
    "realized_vol": 20,
}


def _ohlcv(candles: Sequence[Any]) -> dict[str, np.ndarray]:
    """Extract OHLCV arrays from candles given as dicts or objects."""
    def get(c: Any, key: str) -> float:
        return c[key] if isinstance(c, dict) else getattr(c, key)

    return {
        "open": np.array([get(c, "open") for c in candles], dtype=float),
        "high": np.array([get(c, "high") for c in candles], dtype=float),
        "low": np.array([get(c, "low") for c in candles], dtype=float),
        "close": np.array([get(c, "close") for c in candles], dtype=float),
        "volume": np.array([get(c, "volume") for c in candles], dtype=float),
    }


def compute_indicators(
    candles: Sequence[Any], params: dict | None = None
) -> dict[str, np.ndarray]:
    """Compute the full standard indicator set. Returns name -> aligned array."""
    p = {**DEFAULTS, **(params or {})}
    a = _ohlcv(candles)
    close, high, low, vol = a["close"], a["high"], a["low"], a["volume"]

    fast, slow, signal = p["macd"]
    macd_line, macd_signal, macd_hist = _macd(close, fast, slow, signal)
    bb_n, bb_k = p["bollinger"]
    bb_mid, bb_up, bb_lo, bb_bw = ind.bollinger(close, bb_n, bb_k)
    adx_v, plus_di, minus_di = ind.adx(high, low, close, p["adx"])

    return {
        f"sma_{p['sma']}": ind.sma(close, p["sma"]),
        f"ema_{p['ema']}": ind.ema(close, p["ema"]),
        f"rsi_{p['rsi']}": ind.rsi(close, p["rsi"]),
        "macd": macd_line,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "bb_mid": bb_mid,
        "bb_upper": bb_up,
        "bb_lower": bb_lo,
        "bb_bandwidth": bb_bw,
        f"atr_{p['atr']}": ind.atr(high, low, close, p["atr"]),
        f"adx_{p['adx']}": adx_v,
        "plus_di": plus_di,
        "minus_di": minus_di,
        f"vwap_{p['vwap']}": ind.vwap(high, low, close, vol, p["vwap"]),
        f"realized_vol_{p['realized_vol']}": ind.realized_vol(close, p["realized_vol"]),
    }


def _macd(close: np.ndarray, fast: int, slow: int, signal: int):
    """MACD with a signal line seeded once the MACD line is valid (TA-Lib style)."""
    ema_fast = ind.ema(close, fast)
    ema_slow = ind.ema(close, slow)
    macd_line = ema_fast - ema_slow
    # macd_line is valid from index slow-1; seed the signal EMA there.
    macd_signal = ind._ema_seeded(macd_line, signal, first_valid=slow - 1)
    macd_hist = macd_line - macd_signal
    return macd_line, macd_signal, macd_hist


def _last_finite(arr: np.ndarray) -> float | None:
    finite = np.where(np.isfinite(arr))[0]
    if len(finite) == 0:
        return None
    return float(arr[finite[-1]])


def snapshot(candles: Sequence[Any], params: dict | None = None) -> dict:
    """Latest finite value of each indicator plus provenance metadata."""
    if not candles:
        return {"values": {}, "meta": {"indicator_version": INDICATOR_VERSION, "bars": 0}}

    series = compute_indicators(candles, params)
    values = {name: _last_finite(arr) for name, arr in series.items()}

    last = candles[-1]

    def _attr(obj, key):
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)

    last_ts = _attr(last, "ts")
    source = _attr(last, "source")
    meta = {
        "indicator_version": INDICATOR_VERSION,
        "bars": len(candles),
        "last_ts": last_ts,
        "source": source,
    }
    return {"values": values, "meta": meta}
