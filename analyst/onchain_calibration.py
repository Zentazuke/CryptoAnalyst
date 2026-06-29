"""Does the on-chain divergence signal actually predict price?

Walks historical daily active-address + price data forward and scores the
divergence call (usage rising into a falling price = bullish, and vice-versa)
against the forward price move — the same forward-outcome / CI / significance
treatment the regime and crowd signals get. Strictly causal: the signal at day
``i`` uses only data up to ``i``; the outcome uses ``i+1..i+horizon``.

Returns an ``evidence`` dict (hit-rate, CI, lift, verdict) or None when there is
not enough history. Used to mark the on-chain read measured vs not-yet-measured.
"""
from __future__ import annotations

import numpy as np

from analyst import stats
from analyst.ingestion.coinmetrics import CoinMetricsSource

WIN = 30           # trend window (matches onchain.py)
TREND_THR = 0.02   # divergence threshold (matches onchain.py)


def _causal_trend(arr: np.ndarray, i: int, win: int = WIN) -> float | None:
    if i + 1 < 2 * win:
        return None
    recent = arr[i - win + 1: i + 1].mean()
    prior = arr[i - 2 * win + 1: i - win + 1].mean()
    if prior <= 0:
        return None
    return float(recent / prior - 1.0)


def calibrate_onchain_divergence(asset: str, days: int = 1825, horizon: int = 10,
                                 source: object | None = None) -> dict | None:
    """Forward hit-rate / CI / verdict for the on-chain divergence signal."""
    src = source or CoinMetricsSource()
    rows = src.fetch_metrics(asset.split("_")[0].lower(), ["AdrActCnt", "PriceUSD"], days)
    addr = np.array([r["AdrActCnt"] for r in rows if r.get("AdrActCnt") is not None
                     and r.get("PriceUSD") is not None], float)
    price = np.array([r["PriceUSD"] for r in rows if r.get("AdrActCnt") is not None
                      and r.get("PriceUSD") is not None], float)
    n = len(price)
    if n < 2 * WIN + horizon + 30:
        return None

    bull = bear = hits = 0
    base_up = base_down = base_total = 0
    for i in range(2 * WIN - 1, n - horizon):
        if price[i] <= 0:
            continue
        ret = price[i + horizon] / price[i] - 1.0
        base_total += 1
        base_up += ret > 0
        base_down += ret < 0

        at = _causal_trend(addr, i)
        pt = _causal_trend(price, i)
        if at is None or pt is None:
            continue
        if at > TREND_THR and pt < -TREND_THR:       # bullish divergence
            bull += 1
            hits += ret > 0
        elif at < -TREND_THR and pt > TREND_THR:     # bearish divergence
            bear += 1
            hits += ret < 0

    fired = bull + bear
    if fired == 0 or base_total == 0:
        return None
    p_up = base_up / base_total
    p_down = base_down / base_total
    base_rate = (bull * p_up + bear * p_down) / fired
    ev = stats.evidence(hits, fired, base_rate)
    return {"horizon": horizon, "bullish_signals": bull, "bearish_signals": bear, **ev}
