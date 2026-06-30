"""Realized-volatility forecasting.

Direction on liquid majors is competed to ~zero, but *volatility* is genuinely
forecastable: it clusters and mean-reverts. This module builds an honest vol
forecaster and measures its out-of-sample skill — the same discipline we apply
to every other signal, except this one is expected to clear the bar (and does:
HAR shows positive OOS log-R^2 on BTC/ETH, well above persistence).

Pipeline:
  * ``daily_rv_from_intraday`` — daily realized variance as the sum of squared
    intraday (e.g. hourly) returns. Far less noisy than a single-bar OHLC
    estimate, which makes it actually forecastable.
  * ``har_forecast`` / ``forecast_skill`` — a HAR model (Corsi 2009): the forward
    multi-day realized variance regressed on its own daily / weekly / monthly
    averages, scored strictly out-of-sample in log-variance space vs a
    persistence baseline.
  * ``latest_forecast`` — fit on all history, forecast the next horizon's
    realized vol (annualized) for live use against implied vol (DVOL).

All causal: features at day i use only data up to i; the target is i+1..i+h.
"""
from __future__ import annotations

from typing import Any

import numpy as np

GK_C = 2.0 * np.log(2.0) - 1.0
DAY_MS = 86_400_000
PERIODS_PER_YEAR = {"1h": 8760, "4h": 2190, "12h": 730, "1D": 365, "7D": 52}


def _arr(candles: list[Any], key: str) -> np.ndarray:
    return np.array([(c[key] if isinstance(c, dict) else getattr(c, key)) for c in candles], float)


def daily_rv_from_intraday(candles: list[Any], day_ms: int = DAY_MS) -> tuple[np.ndarray, np.ndarray]:
    """Daily realized variance = sum of squared intraday log returns per UTC day.

    Returns (day_start_ms, rv) oldest first. Feed it hourly candles."""
    ts = _arr(candles, "ts")
    cl = _arr(candles, "close")
    if len(cl) < 3:
        return np.array([]), np.array([])
    ret = np.diff(np.log(cl))
    day = (ts[1:] // day_ms).astype(np.int64)
    days = np.unique(day)
    rv = np.array([float(np.sum(ret[day == d] ** 2)) for d in days])
    keep = np.isfinite(rv) & (rv > 0)
    return (days[keep] * day_ms).astype(np.int64), rv[keep]


def gk_variance(candles: list[Any]) -> np.ndarray:
    """Per-bar Garman-Klass variance (alternative estimator when no intraday)."""
    o, h, low, cl = (_arr(candles, k) for k in ("open", "high", "low", "close"))
    with np.errstate(divide="ignore", invalid="ignore"):
        hl, co = np.log(h / low), np.log(cl / o)
        var = 0.5 * hl * hl - GK_C * co * co
    return np.where(np.isfinite(var) & (var > 0), var, np.nan)


def _har_features(rv: np.ndarray) -> np.ndarray:
    """Causal HAR regressors per day: [1, rv_daily, rv_weekly(5), rv_monthly(22)]."""
    n = len(rv)

    def roll(win: int) -> np.ndarray:
        out = np.full(n, np.nan)
        for i in range(n):
            seg = rv[max(0, i - win + 1): i + 1]
            seg = seg[np.isfinite(seg)]
            if len(seg) >= max(1, win // 2):
                out[i] = seg.mean()
        return out

    return np.column_stack([np.ones(n), roll(1), roll(5), roll(22)])


def _forward_mean(rv: np.ndarray, horizon: int) -> np.ndarray:
    n = len(rv)
    tgt = np.full(n, np.nan)
    for i in range(n - horizon):
        seg = rv[i + 1: i + 1 + horizon]
        if np.all(np.isfinite(seg)):
            tgt[i] = seg.mean()
    return tgt


def _r2_log(pred: np.ndarray, actual: np.ndarray) -> float:
    lp, la = np.log(pred + 1e-12), np.log(actual + 1e-12)
    ss_res = np.sum((la - lp) ** 2)
    ss_tot = np.sum((la - la.mean()) ** 2)
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def har_forecast(rv: np.ndarray, horizon: int = 5, train_frac: float = 0.6):
    """Fit HAR on the early fraction, forecast forward variance OOS.
    Returns (preds, actual, test_idx, beta) or None if too little data."""
    X = _har_features(rv)
    tgt = _forward_mean(rv, horizon)
    rows = np.isfinite(tgt) & np.all(np.isfinite(X), axis=1)
    idx = np.where(rows)[0]
    if len(idx) < 120:
        return None
    sp = int(len(idx) * train_frac)
    tr, te = idx[:sp], idx[sp:]
    beta, *_ = np.linalg.lstsq(X[tr], tgt[tr], rcond=None)
    preds = np.clip(X[te] @ beta, 1e-12, None)
    return preds, tgt[te], te, beta


def forecast_skill(rv: np.ndarray, horizon: int = 5, train_frac: float = 0.6) -> dict | None:
    """Out-of-sample HAR skill vs persistence (next variance = recent weekly avg)."""
    out = har_forecast(rv, horizon, train_frac)
    if out is None:
        return None
    preds, actual, te, beta = out
    persistence = np.clip(_har_features(rv)[te, 2], 1e-12, None)
    har_r2 = _r2_log(preds, actual)
    pers_r2 = _r2_log(persistence, actual)
    return {
        "horizon": horizon,
        "n_test": int(len(te)),
        "har_r2_log": round(har_r2, 4),
        "persistence_r2_log": round(pers_r2, 4),
        "har_beats_persistence": har_r2 > pers_r2,
        "beta": {"const": round(float(beta[0]), 8), "daily": round(float(beta[1]), 4),
                 "weekly": round(float(beta[2]), 4), "monthly": round(float(beta[3]), 4)},
    }


def latest_forecast(rv: np.ndarray, horizon: int = 5, timeframe: str = "1D") -> dict | None:
    """Fit on all history; forecast the next `horizon`-day realized vol (annualized %)."""
    X = _har_features(rv)
    tgt = _forward_mean(rv, horizon)
    rows = np.isfinite(tgt) & np.all(np.isfinite(X), axis=1)
    if rows.sum() < 120 or not np.all(np.isfinite(X[-1])):
        return None
    beta, *_ = np.linalg.lstsq(X[rows], tgt[rows], rcond=None)
    var_pred = float(max(1e-12, X[-1] @ beta))  # forecast forward per-day variance
    ann = float(np.sqrt(var_pred * PERIODS_PER_YEAR.get(timeframe, 365)) * 100.0)
    return {"horizon": horizon, "forecast_variance": var_pred, "forecast_vol_annual": round(ann, 1)}
