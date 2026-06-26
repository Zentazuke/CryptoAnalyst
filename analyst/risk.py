"""Expected move + risk framing.

Pure volatility math — never a prediction. Gives the 1-sigma expected range over
the horizon (from realized vol), the volatility regime (Bollinger-bandwidth
percentile: compressed vs expanding), and reward-in-ATR (R-multiple) to the
nearest key level for both a long and a short. Answers "if you act, here's the
math," using pieces already computed (ATR, realized vol, levels).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from analyst.features import indicators as ind


def _dp(price: float) -> int:
    if price >= 1000:
        return 0
    if price >= 1:
        return 2
    if price >= 0.01:
        return 4
    return 6


def risk_frame(
    candles: list[Any], levels: dict | None = None, horizon: int = 24,
    rv_window: int = 100, bw_window: int = 120,
) -> dict | None:
    def col(key):
        return np.array([c[key] if isinstance(c, dict) else getattr(c, key) for c in candles], float)
    high, low, close = col("high"), col("low"), col("close")
    n = len(close)
    if n < 40:
        return None

    price = float(close[-1])
    d = _dp(price)
    atr = ind.atr(high, low, close, 14)
    atr_v = float(atr[-1]) if np.isfinite(atr[-1]) and atr[-1] > 0 else price * 0.01

    logret = np.diff(np.log(close))
    rv = float(np.std(logret[-rv_window:], ddof=0)) if len(logret) >= 20 else 0.0
    exp_pct = rv * math.sqrt(horizon)

    _, _, _, bw = ind.bollinger(close, 20)
    bw_now = bw[-1]
    valid = bw[np.isfinite(bw)][-bw_window:]
    bw_rank = float((valid <= bw_now).mean()) if (len(valid) >= 10 and np.isfinite(bw_now)) else None
    vol_regime = ("compressed" if bw_rank is not None and bw_rank <= 0.25
                  else "elevated" if bw_rank is not None and bw_rank >= 0.75 else "normal")

    nr = (levels or {}).get("nearest_resistance")
    ns = (levels or {}).get("nearest_support")
    long_rr = round((nr["price"] - price) / atr_v, 2) if nr and atr_v > 0 else None
    short_rr = round((price - ns["price"]) / atr_v, 2) if ns and atr_v > 0 else None

    return {
        "price": round(price, d),
        "horizon": horizon,
        "expected_move_pct": round(exp_pct, 4),
        "band_low": round(price * (1 - exp_pct), d),
        "band_high": round(price * (1 + exp_pct), d),
        "atr": round(atr_v, d),
        "atr_pct": round(atr_v / price, 4),
        "vol_regime": vol_regime,
        "bandwidth_pct": round(bw_rank, 3) if bw_rank is not None else None,
        "long": {"stop": round(price - atr_v, d),
                 "target": nr["price"] if nr else None, "rr": long_rr},
        "short": {"stop": round(price + atr_v, d),
                  "target": ns["price"] if ns else None, "rr": short_rr},
    }
