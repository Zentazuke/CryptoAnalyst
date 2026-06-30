"""Tail management for the short-vol harvest, by structure rather than timing.

Step 3 showed an entry-time risk gate can't dodge the crash months. The honest
alternatives are structural:

  * ``defined_risk_pnl`` — cap each trade's loss at ``max_loss`` (you sold a
    spread / bought a far tail hedge), paying ``hedge_cost`` every trade for it.
  * ``dynamic_exit_pnl`` — mark the trade daily and cut it if the running loss
    breaches ``stop_loss`` (how real desks manage it), at the price of whipsaws.

Both are approximations in vol-point space (a vol-swap proxy, not a real option
chain), so treat the levels as directional, not precise. ``run_vrp_exit`` runs
non-overlapping trades through a chosen model for an apples-to-apples Sharpe/DD.
"""
from __future__ import annotations

import math

import numpy as np

from analyst.vrp_backtest import vrp_metrics


def _realized_vol(rets: np.ndarray, t: int, k: int) -> float:
    seg = rets[t: t + k]
    return float(np.std(seg, ddof=0) * math.sqrt(365) * 100.0)


def hold_to_expiry_pnl(rets, t, horizon, implied, cost) -> float:
    return implied - _realized_vol(rets, t, horizon) - cost


def defined_risk_pnl(rets, t, horizon, implied, cost, *, max_loss: float, hedge_cost: float) -> float:
    """Loss capped at -max_loss (a spread / tail hedge), paid for via hedge_cost."""
    raw = hold_to_expiry_pnl(rets, t, horizon, implied, cost)
    return max(raw, -abs(max_loss)) - hedge_cost


def dynamic_exit_pnl(rets, t, horizon, implied, cost, *, stop_loss: float,
                     min_days: int = 5, exit_cost: float = 1.0) -> float:
    """Cut the trade early once the running mark breaches -stop_loss."""
    for k in range(min_days, horizon):
        if len(rets[t: t + k]) < k:
            break
        running = implied - _realized_vol(rets, t, k) - cost
        if running <= -abs(stop_loss):
            return -abs(stop_loss) - exit_cost
    return hold_to_expiry_pnl(rets, t, horizon, implied, cost)


def run_vrp_exit(dvol_by_day, day_index, closes, horizon, cost, pnl_fn) -> dict | None:
    """Non-overlapping VRP harvest using a chosen per-trade P&L model."""
    rets = np.diff(np.log(closes))
    n = len(closes)
    trades: list[dict] = []
    t = 0
    while t < n - horizon - 1:
        iv = dvol_by_day.get(int(day_index[t]))
        if iv is not None and len(rets[t: t + horizon]) == horizon:
            trades.append({"t": t, "pnl": pnl_fn(rets, t, horizon, iv, cost)})
        t += horizon
    return vrp_metrics(trades, horizon)
