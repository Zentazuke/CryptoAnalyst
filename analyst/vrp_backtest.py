"""Variance-risk-premium harvest backtest.

The measured edge: implied vol (DVOL) sits systematically above the realized vol
that follows. This backtests *selling* that overpriced vol, honestly:

  * non-overlapping holding periods, so the Sharpe is real (overlapping windows
    inflate it),
  * gross AND net of a per-trade cost (option spread/skew/fees, in vol points),
  * the left tail made explicit — max drawdown and worst single trade, because
    that tail is exactly what kills naive short-vol,
  * an optional ``gate`` (a per-day "is it safe to sell vol?" mask) so we can
    later measure what the analyst's risk-state read adds.

P&L convention: a short vol-swap held to expiry pays ``implied - realized`` (vol
points) minus cost. Vol-linear, the conservative/intuitive choice; variance
swaps would amplify both the premium and the tail.
"""
from __future__ import annotations

import math

import numpy as np


def forward_realized_vol(rets: np.ndarray, t: int, horizon: int) -> float | None:
    """Annualized realized vol (%) over the next `horizon` daily returns from t."""
    fwd = rets[t: t + horizon]
    if len(fwd) < horizon:
        return None
    return float(np.std(fwd, ddof=0) * math.sqrt(365) * 100.0)


def build_trades(dvol_by_day: dict[int, float], day_index: np.ndarray, closes: np.ndarray,
                 horizon: int = 30, cost_vol_pts: float = 2.0,
                 gate_ok: np.ndarray | None = None) -> list[dict]:
    """Non-overlapping short-vol trades. ``gate_ok[t]`` False skips that entry."""
    rets = np.diff(np.log(closes))
    trades: list[dict] = []
    n = len(closes)
    t = 0
    while t < n - horizon - 1:
        d = int(day_index[t])
        iv = dvol_by_day.get(d)
        if iv is not None and (gate_ok is None or bool(gate_ok[t])):
            rv = forward_realized_vol(rets, t, horizon)
            if rv is not None:
                trades.append({"t": t, "day": d, "implied": iv, "realized": rv,
                               "pnl": iv - rv - cost_vol_pts})
        t += horizon  # non-overlapping
    return trades


def vrp_metrics(trades: list[dict], horizon: int) -> dict | None:
    """Honest summary: mean P&L, hit rate, annualized Sharpe, drawdown, worst trade."""
    if len(trades) < 8:
        return None
    pnl = np.array([x["pnl"] for x in trades], float)
    cum = np.cumsum(pnl)
    peak = np.maximum.accumulate(cum)
    dd = cum - peak
    mean, sd = float(pnl.mean()), float(pnl.std(ddof=1))
    trades_per_year = 365.0 / horizon
    sharpe = (mean / sd) * math.sqrt(trades_per_year) if sd > 0 else float("nan")
    return {
        "n_trades": len(trades),
        "mean_pnl_volpts": round(mean, 2),
        "hit_rate": round(float((pnl > 0).mean()), 3),
        "ann_sharpe": round(sharpe, 2),
        "total_pnl_volpts": round(float(cum[-1]), 1),
        "max_drawdown_volpts": round(float(dd.min()), 1),
        "worst_trade_volpts": round(float(pnl.min()), 1),
        "best_trade_volpts": round(float(pnl.max()), 1),
    }


def run_vrp(dvol_by_day: dict[int, float], day_index: np.ndarray, closes: np.ndarray,
            horizon: int = 30, cost_vol_pts: float = 2.0,
            gate_ok: np.ndarray | None = None) -> dict | None:
    """Build trades and summarize, in one call."""
    trades = build_trades(dvol_by_day, day_index, closes, horizon, cost_vol_pts, gate_ok)
    m = vrp_metrics(trades, horizon)
    if m is None:
        return None
    return {"horizon": horizon, "cost_vol_pts": cost_vol_pts, **m}
