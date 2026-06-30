"""Tests for the structural tail-cap exit models (synthetic, no network)."""
import numpy as np

from analyst.vol_exit import (
    hold_to_expiry_pnl, defined_risk_pnl, dynamic_exit_pnl, run_vrp_exit,
)


def _rets(n=400, sigma=0.02, seed=0):
    return np.random.default_rng(seed).normal(0, sigma, n)


def test_defined_risk_caps_a_big_loss():
    rets = _rets()
    # a trade where realized blows out: implied low, realized high
    t = 0
    # force a high *variance* (alternating signs, not a constant drift)
    rets[t:t + 30] = 0.10 * (-1.0) ** np.arange(30)
    raw = hold_to_expiry_pnl(rets, t, 30, implied=50, cost=2)
    capped = defined_risk_pnl(rets, t, 30, 50, 2, max_loss=15, hedge_cost=1.5)
    assert raw < -100              # naked loss is huge
    assert capped == -15 - 1.5     # capped + hedge cost


def test_defined_risk_haircut_on_winners():
    rets = _rets(sigma=0.01)  # calm -> realized well below implied
    win = hold_to_expiry_pnl(rets, 0, 30, implied=60, cost=2)
    capped = defined_risk_pnl(rets, 0, 30, 60, 2, max_loss=15, hedge_cost=1.5)
    assert capped == win - 1.5  # winners just pay the hedge


def test_dynamic_exit_stops_out_on_spike():
    rets = _rets(sigma=0.005)
    rets[5:12] = 0.12 * (-1.0) ** np.arange(7)  # violent (high-variance) move mid-trade
    pnl = dynamic_exit_pnl(rets, 0, 30, implied=45, cost=2, stop_loss=12, exit_cost=1.0)
    assert pnl == -12 - 1.0  # stopped out at the cap


def test_dynamic_exit_holds_when_calm():
    rets = _rets(sigma=0.01, seed=3)
    pnl = dynamic_exit_pnl(rets, 0, 30, implied=60, cost=2, stop_loss=20)
    held = hold_to_expiry_pnl(rets, 0, 30, 60, 2)
    assert abs(pnl - held) < 1e-9  # never breached -> same as hold


def test_run_vrp_exit_produces_metrics():
    di = np.arange(600, dtype=np.int64)
    closes = 100 * np.exp(np.cumsum(_rets(600, 0.02)))
    dvol = {int(d): 60.0 for d in di}
    m = run_vrp_exit(dvol, di, closes, 30, 2.0,
                     lambda r, t, h, iv, c: hold_to_expiry_pnl(r, t, h, iv, c))
    assert m is not None and m["n_trades"] > 8
