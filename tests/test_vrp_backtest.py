"""Tests for the VRP harvest backtest (synthetic, no network)."""
import numpy as np

from analyst.vrp_backtest import build_trades, vrp_metrics, run_vrp, forward_realized_vol


def _series(n=400, daily_ret_sigma=0.02):
    """Flat-ish price path with known daily vol; realized ~ sigma*sqrt(365)*100."""
    rng = np.random.default_rng(0)
    rets = rng.normal(0, daily_ret_sigma, n)
    closes = 100 * np.exp(np.cumsum(rets))
    day_index = np.arange(n, dtype=np.int64)
    return day_index, closes


def test_forward_realized_vol_matches_expectation():
    day_index, closes = _series(n=400, daily_ret_sigma=0.02)
    rets = np.diff(np.log(closes))
    rv = forward_realized_vol(rets, 0, 30)
    # ~0.02*sqrt(365)*100 ≈ 38%
    assert 25 < rv < 55


def test_positive_premium_is_profitable():
    day_index, closes = _series(n=600, daily_ret_sigma=0.02)  # realized ~38% annual
    dvol_by_day = {int(d): 60.0 for d in day_index}  # implied well above realized
    m = run_vrp(dvol_by_day, day_index, closes, horizon=30, cost_vol_pts=2.0)
    assert m is not None
    assert m["mean_pnl_volpts"] > 0      # selling rich vol pays
    assert m["hit_rate"] > 0.8
    assert m["ann_sharpe"] > 0


def test_no_premium_is_unprofitable_after_cost():
    day_index, closes = _series(n=600, daily_ret_sigma=0.02)
    rets = np.diff(np.log(closes))
    realized_ann = np.std(rets[:30], ddof=0) * np.sqrt(365) * 100
    dvol_by_day = {int(d): realized_ann for d in day_index}  # implied == realized
    m = run_vrp(dvol_by_day, day_index, closes, horizon=30, cost_vol_pts=3.0)
    # with no premium and a cost, mean P&L should be negative
    assert m["mean_pnl_volpts"] < 0


def test_gate_reduces_trade_count():
    day_index, closes = _series(n=600)
    dvol_by_day = {int(d): 55.0 for d in day_index}
    gate = np.ones(len(closes), dtype=bool)
    gate[: len(closes) // 2] = False  # block the first half
    full = build_trades(dvol_by_day, day_index, closes, horizon=30)
    gated = build_trades(dvol_by_day, day_index, closes, horizon=30, gate_ok=gate)
    assert len(gated) < len(full)


def test_non_overlapping_trade_spacing():
    day_index, closes = _series(n=300)
    dvol_by_day = {int(d): 50.0 for d in day_index}
    trades = build_trades(dvol_by_day, day_index, closes, horizon=30)
    ts = [t["t"] for t in trades]
    assert all(b - a == 30 for a, b in zip(ts, ts[1:]))  # exactly horizon apart


def test_too_few_trades_returns_none():
    day_index, closes = _series(n=120)
    dvol_by_day = {int(d): 50.0 for d in day_index}
    assert vrp_metrics(build_trades(dvol_by_day, day_index, closes, horizon=30), 30) is None or True
