"""Backtest each alert type: does the setup actually resolve as expected?

Reconstructs each alert's firing condition causally over history (same logic as
``alerts.detect_alerts``) and scores the vol-scaled forward outcome in the
setup's expected direction — hit-rate vs base rate vs lift. Turns the alert feed
from heuristics into measured setups.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from analyst import stats
from analyst.features import indicators as ind
from analyst.regime import classify_series
from analyst.regime import classifier as C
from analyst.regime.derivatives import align_funding

# alert type -> expected direction (+1 up, -1 down)
DIRECTION = {
    "trend-up": 1, "trend-down": -1,
    "crowded-long": -1, "crowded-short": 1,
    "rsi-oversold": 1, "rsi-overbought": -1,
}


def calibrate_alerts(
    candles: list[Any], funding_rows: list[dict] | None = None,
    horizon: int = 12, k: float = 1.0, lookback: int = 30,
    mom_thr: float = 0.03, funding_extreme: float = 0.0003,
) -> dict | None:
    def col(key):
        return np.array([c[key] if isinstance(c, dict) else getattr(c, key) for c in candles], float)
    ts = [c["ts"] if isinstance(c, dict) else c.ts for c in candles]
    high, low, close = col("high"), col("low"), col("close")
    n = len(close)
    if n < lookback + horizon + 30:
        return None

    atr = ind.atr(high, low, close, 14)
    rsi = ind.rsi(close, 14)
    ema = ind.ema(close, 20)
    labels = [r.label for r in classify_series(candles)]
    funding = align_funding(ts, funding_rows) if funding_rows else np.full(n, np.nan)
    mom = np.full(n, np.nan)
    for i in range(lookback, n):
        if close[i - lookback] > 0:
            mom[i] = close[i] / close[i - lookback] - 1.0

    tu = np.array([lab == C.TREND_UP for lab in labels])
    td = np.array([lab == C.TREND_DOWN for lab in labels])
    rng = np.array([lab in (C.RANGE, C.LOW_VOL_DRIFT) for lab in labels])
    fe, fr = np.isfinite(ema), np.isfinite(rsi)
    above = fe & (close > ema)
    below = fe & (close < ema)
    mom_up = np.isfinite(mom) & (mom > mom_thr)
    mom_dn = np.isfinite(mom) & (mom < -mom_thr)
    ff = np.isfinite(funding)

    bull = tu.astype(int) + mom_up.astype(int) + above.astype(int) + (fr & (rsi >= 50) & (rsi < 70)).astype(int)
    bear = td.astype(int) + mom_dn.astype(int) + below.astype(int) + (fr & (rsi > 30) & (rsi <= 50)).astype(int)

    fires = {
        "trend-up": bull >= 3,
        "trend-down": bear >= 3,
        "crowded-long": ff & (funding > funding_extreme) & ((fr & (rsi > 65)) | tu),
        "crowded-short": ff & (funding < -funding_extreme) & ((fr & (rsi < 35)) | rng),
        "rsi-oversold": fr & (rsi < 20),
        "rsi-overbought": fr & (rsi > 80),
    }

    sqrt_h = math.sqrt(horizon)

    def evaluate(fire: np.ndarray, sign: int) -> dict | None:
        hits = fired = base_match = base_total = 0
        for i in range(n - horizon):
            if not (np.isfinite(close[i]) and np.isfinite(atr[i]) and close[i] > 0 and atr[i] > 0):
                continue
            thr = k * (atr[i] / close[i]) * sqrt_h
            ret = close[i + horizon] / close[i] - 1.0
            ok = ret > thr if sign > 0 else ret < -thr
            base_total += 1
            base_match += ok
            if fire[i]:
                fired += 1
                hits += ok
        if fired == 0 or base_total == 0:
            return None
        hit_rate = hits / fired
        base_rate = base_match / base_total
        ev = stats.evidence(int(hits), int(fired), base_rate)
        return {"count": fired, "hit_rate": round(hit_rate, 4),
                "base_rate": round(base_rate, 4),
                "lift": round(hit_rate / base_rate, 3) if base_rate > 0 else None,
                "ci_low": ev["ci_low"], "ci_high": ev["ci_high"],
                "significant": ev["significant"], "verdict": ev["verdict"]}

    return {"horizon": horizon, "per_type": {key: evaluate(fires[key], DIRECTION[key]) for key in DIRECTION}}


def aggregate_track_records(reports: list[dict | None]) -> dict:
    """Combine several per-symbol calibrations into one per-type track record."""
    out: dict[str, dict] = {}
    for t in DIRECTION:
        cnt = 0
        hw = bw = 0.0
        for rep in reports:
            st = rep["per_type"].get(t) if rep else None
            if st and st.get("count"):
                cnt += st["count"]
                hw += st["hit_rate"] * st["count"]
                bw += st["base_rate"] * st["count"]
        if cnt:
            hr, br = hw / cnt, bw / cnt
            out[t] = {"count": cnt, "hit_rate": round(hr, 4), "base_rate": round(br, 4),
                      "lift": round(hr / br, 3) if br > 0 else None}
    return out

