"""Structural price levels: the support/resistance a trader actually watches.

Combines confirmed swing pivots, the recent range edges, a volume-profile point
of control, and nearby round numbers, then clusters nearby levels into zones and
returns the nearest support/resistance relative to the current price (with
distance in % and in ATR). Pivots are confirmed (need bars on both sides), so a
"level" is something price has already reacted to — not a guess about the future.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from analyst.features import indicators as ind


def _arrays(candles: list[Any]) -> dict[str, np.ndarray]:
    def g(c: Any, k: str) -> float:
        return c[k] if isinstance(c, dict) else getattr(c, k)

    return {k: np.array([g(c, k) for c in candles], float) for k in ("high", "low", "close", "volume")}


def _dp(price: float) -> int:
    if price >= 1000:
        return 0
    if price >= 1:
        return 2
    if price >= 0.01:
        return 4
    return 6


def swing_pivots(high: np.ndarray, low: np.ndarray, k: int = 3) -> tuple[list[float], list[float]]:
    """Confirmed swing-high and swing-low prices (extremum over ±k bars)."""
    highs, lows = [], []
    n = len(high)
    for i in range(k, n - k):
        if high[i] == high[i - k:i + k + 1].max():
            highs.append(float(high[i]))
        if low[i] == low[i - k:i + k + 1].min():
            lows.append(float(low[i]))
    return highs, lows


def volume_poc(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, bins: int = 40) -> float | None:
    """Volume-profile point of control: the price bin with the most traded volume."""
    lo, hi = float(low.min()), float(high.max())
    if hi <= lo:
        return None
    edges = np.linspace(lo, hi, bins + 1)
    typical = (high + low + close) / 3.0
    idx = np.clip(np.digitize(typical, edges) - 1, 0, bins - 1)
    vol_by_bin = np.zeros(bins)
    for b, v in zip(idx, volume):
        vol_by_bin[b] += v
    peak = int(vol_by_bin.argmax())
    return float((edges[peak] + edges[peak + 1]) / 2.0)


def round_levels(price: float) -> list[float]:
    """The round numbers bracketing the current price (psychological levels)."""
    if price <= 0:
        return []
    step = 10 ** (math.floor(math.log10(price)) - 1)  # decade/10
    base = math.floor(price / step) * step
    return [round(base, 10), round(base + step, 10)]


def _cluster(levels: list[dict], tol_pct: float) -> list[dict]:
    """Merge levels within ``tol_pct`` of each other into zones (touch = strength)."""
    levels = sorted(levels, key=lambda x: x["price"])
    clusters: list[dict] = []
    for lv in levels:
        if clusters and abs(lv["price"] - clusters[-1]["ref"]) / clusters[-1]["ref"] <= tol_pct:
            c = clusters[-1]
            c["members"].append(lv)
            w = sum(m["weight"] for m in c["members"])
            c["ref"] = sum(m["price"] * m["weight"] for m in c["members"]) / w
        else:
            clusters.append({"ref": lv["price"], "members": [lv]})
    out = []
    for c in clusters:
        types = sorted({m["type"] for m in c["members"]})
        out.append({
            "price": round(c["ref"], _dp(c["ref"])),
            "types": types,
            "touches": len(c["members"]),
        })
    return out


def key_levels(
    candles: list[Any], swing_k: int = 3, lookback: int = 240, tol_pct: float = 0.004,
) -> dict:
    """Assemble clustered support/resistance around the current price."""
    if len(candles) < swing_k * 2 + 5:
        return {"price": None, "support": [], "resistance": [],
                "nearest_support": None, "nearest_resistance": None, "levels": []}

    a = _arrays(candles)
    high, low, close, vol = a["high"], a["low"], a["close"], a["volume"]
    s = slice(-lookback, None)
    h, l, c, v = high[s], low[s], close[s], vol[s]
    price = float(c[-1])
    atr = ind.atr(high, low, close, 14)
    atr_v = float(atr[-1]) if np.isfinite(atr[-1]) and atr[-1] > 0 else price * 0.01

    raw: list[dict] = []
    ph, pl = swing_pivots(h, l, swing_k)
    raw += [{"price": p, "type": "swing high", "weight": 1.0} for p in ph]
    raw += [{"price": p, "type": "swing low", "weight": 1.0} for p in pl]
    raw.append({"price": float(h.max()), "type": "range high", "weight": 2.0})
    raw.append({"price": float(l.min()), "type": "range low", "weight": 2.0})
    poc = volume_poc(h, l, c, v)
    if poc is not None:
        raw.append({"price": poc, "type": "volume POC", "weight": 2.0})
    raw += [{"price": r, "type": "round number", "weight": 0.8} for r in round_levels(price)]

    clustered = _cluster(raw, tol_pct)
    for lv in clustered:
        lv["dist_pct"] = round((lv["price"] - price) / price, 4)
        lv["dist_atr"] = round((lv["price"] - price) / atr_v, 2)

    support = sorted((lv for lv in clustered if lv["price"] < price), key=lambda x: -x["price"])
    resistance = sorted((lv for lv in clustered if lv["price"] > price), key=lambda x: x["price"])

    return {
        "price": price,
        "atr": round(atr_v, _dp(atr_v)),
        "support": support[:5],
        "resistance": resistance[:5],
        "nearest_support": support[0] if support else None,
        "nearest_resistance": resistance[0] if resistance else None,
        "levels": clustered,
    }
