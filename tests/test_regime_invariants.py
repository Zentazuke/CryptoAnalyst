"""Invariant tests: the classifier must call obvious regimes correctly."""
from __future__ import annotations

import numpy as np

from analyst.regime import classify_series
from analyst.regime import classifier as C

HOUR_MS = 3_600_000
START = 1_700_000_000_000


def _candles(close, high=None, low=None, vol=None):
    n = len(close)
    high = close * 1.002 if high is None else high
    low = close * 0.998 if low is None else low
    vol = np.full(n, 100.0) if vol is None else vol
    out = []
    for i in range(n):
        out.append({
            "ts": START + i * HOUR_MS,
            "open": float(close[i - 1]) if i else float(close[0]),
            "high": float(max(high[i], close[i])),
            "low": float(min(low[i], close[i])),
            "close": float(close[i]),
            "volume": float(vol[i]),
        })
    return out


def test_strong_uptrend_is_trend_up():
    close = 100.0 * (1.0 + np.linspace(0, 0.8, 200))  # steady climb
    labels = [r.label for r in classify_series(_candles(close))]
    assert labels[-1] == C.TREND_UP


def test_strong_downtrend_is_trend_down():
    close = 100.0 * (1.0 - np.linspace(0, 0.6, 200))
    labels = [r.label for r in classify_series(_candles(close))]
    assert labels[-1] == C.TREND_DOWN


def test_choppy_meanreverting_is_range_or_lowvol():
    # Mean-reverting noise: frequent reversals -> low ADX -> non-trending.
    rng = np.random.default_rng(2)
    close = np.empty(220)
    close[0] = 100.0
    for i in range(1, 220):
        close[i] = close[i - 1] + 0.15 * (100.0 - close[i - 1]) + rng.normal(0, 0.5)
    labels = [r.label for r in classify_series(_candles(close))]
    assert labels[-1] in (C.RANGE, C.LOW_VOL_DRIFT)


def test_volatility_shock_is_flash_risk():
    rng = np.random.default_rng(0)
    close = 100.0 + np.cumsum(rng.normal(0, 0.2, 120))
    high = close * 1.002
    low = close * 0.998
    vol = np.full(120, 100.0)
    # inject a violent down bar on a volume spike at the end
    close[-1] = close[-2] * 0.88
    low[-1] = close[-1] * 0.99
    high[-1] = close[-2] * 1.001
    vol[-1] = 1500.0
    res = classify_series(_candles(close, high, low, vol))
    assert res[-1].label == C.FLASH_RISK
    assert res[-1].confidence > 0


def test_every_result_has_reasons_and_confidence_range():
    close = 100.0 + np.cumsum(np.random.default_rng(1).normal(0, 0.3, 120))
    for r in classify_series(_candles(close)):
        assert 0.0 <= r.confidence <= 1.0
        assert r.reasons
        assert r.label in C.LABELS
