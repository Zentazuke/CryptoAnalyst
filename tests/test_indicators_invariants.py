"""Invariant tests: externally-obvious properties that must always hold."""
from __future__ import annotations

import numpy as np

from analyst.features import indicators as ind
from analyst.features.engine import _macd


def test_constant_series_invariants():
    n = 60
    c = np.full(n, 5.0)
    # moving averages of a constant equal the constant
    assert np.isclose(ind.sma(c, 20)[-1], 5.0)
    assert np.isclose(ind.ema(c, 20)[-1], 5.0)
    # flat market -> neutral RSI
    assert np.isclose(ind.rsi(c, 14)[-1], 50.0)
    # no dispersion -> zero band width, middle on price
    mid, upper, lower, bw = ind.bollinger(c, 20)
    assert np.isclose(mid[-1], 5.0) and np.isclose(bw[-1], 0.0)
    # no range -> zero ATR ; no momentum -> zero MACD ; no variance -> zero vol
    assert np.isclose(ind.atr(c, c, c, 14)[-1], 0.0)
    macd_line, _, hist = _macd(c, 12, 26, 9)
    assert np.isclose(macd_line[-1], 0.0) and np.isclose(hist[-1], 0.0)
    assert np.isclose(ind.realized_vol(c, 20)[-1], 0.0)


def test_monotonic_up_rsi_is_100():
    c = np.arange(1, 80, dtype=float)
    assert np.isclose(ind.rsi(c, 14)[-1], 100.0)


def test_monotonic_down_rsi_is_0():
    c = np.arange(80, 1, -1, dtype=float)
    assert np.isclose(ind.rsi(c, 14)[-1], 0.0)


def test_uptrend_plus_di_dominates():
    n = 80
    base = np.arange(n, dtype=float) + 100.0
    high = base + 1.0
    low = base - 1.0
    close = base + 0.5
    adx_v, plus_di, minus_di = ind.adx(high, low, close, 14)
    assert plus_di[-1] > minus_di[-1]


def test_warmup_is_nan():
    c = np.arange(1, 50, dtype=float)
    assert np.isnan(ind.sma(c, 20)[18])      # before index 19
    assert np.isnan(ind.ema(c, 20)[18])
    assert np.isnan(ind.rsi(c, 14)[13])      # before index 14
    assert np.isnan(ind.atr(c, c, c, 14)[12])
