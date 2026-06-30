"""Tests for the vol-selling risk gate (synthetic, no network)."""
import numpy as np

from analyst.risk_gate import vol_sell_gate


def _candles(closes):
    return [{"open": c, "high": c * 1.005, "low": c * 0.995, "close": c, "volume": 1.0,
             "ts": i * 86_400_000} for i, c in enumerate(closes)]


def test_calm_market_is_mostly_sellable():
    rng = np.random.default_rng(0)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.005, 300)))  # quiet
    ok = vol_sell_gate(_candles(closes), use_regime=False)
    assert ok.mean() > 0.8  # mostly safe to sell


def test_vol_acceleration_triggers_standaside():
    calm = 100 * np.exp(np.cumsum(np.full(120, 0.0)))  # flat
    rng = np.random.default_rng(1)
    spike = calm[-1] * np.exp(np.cumsum(rng.normal(0, 0.08, 30)))  # sudden high vol
    closes = np.concatenate([calm, spike])
    ok = vol_sell_gate(_candles(closes), use_drawdown=False, use_regime=False)
    # during/after the spike the gate should stand aside at least sometimes
    assert ok[125:150].mean() < ok[:115].mean()


def test_drawdown_triggers_standaside():
    up = np.linspace(100, 150, 80)
    crash = np.linspace(150, 110, 20)  # ~27% drawdown
    closes = np.concatenate([up, crash])
    ok = vol_sell_gate(_candles(closes), use_vol_accel=False, use_regime=False, dd_thresh=0.12)
    assert not ok[-1]  # deep in a drawdown -> stand aside


def test_components_can_be_disabled():
    closes = 100 * np.exp(np.cumsum(np.full(200, 0.0)))
    ok = vol_sell_gate(_candles(closes), use_vol_accel=False, use_drawdown=False, use_regime=False)
    assert ok.all()  # nothing enabled -> always sellable
