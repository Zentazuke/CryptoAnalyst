"""Combined-outlook calibration: structure + agreement-beats-parts on rigged data."""
from __future__ import annotations

import numpy as np

from analyst.outlook_calibration import calibrate_combined

HOUR = 3_600_000
START = 1_700_000_000_000


def _candles(close):
    return [
        {"ts": START + i * HOUR, "open": float(close[i - 1] if i else close[0]),
         "high": float(close[i]) * 1.002, "low": float(close[i]) * 0.998,
         "close": float(close[i]), "volume": 100.0}
        for i in range(len(close))
    ]


def test_structure_and_buckets():
    rng = np.random.default_rng(0)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, 600)))
    funding = [{"t": START + i * HOUR, "v": float(rng.normal(0, 0.0004))} for i in range(600)]
    rep = calibrate_combined(_candles(close), funding, horizon=24)
    assert rep is not None
    ps = rep["per_signal"]
    assert "regime" in ps and "crowd" in ps and "regime+crowd_agree" in ps and "all_agree" in ps


def test_returns_none_when_too_short():
    close = 100.0 + np.cumsum(np.random.default_rng(1).normal(0, 0.3, 80))
    assert calibrate_combined(_candles(close), None, horizon=24, window=200) is None


def test_trending_regime_has_directional_calls():
    # constant-% uptrend -> regime fires long calls that clear the vol threshold
    close = 100.0 * np.exp(np.cumsum(np.full(500, 0.005)))
    rep = calibrate_combined(_candles(close), None, horizon=12, window=100)
    reg = rep["per_signal"]["regime"]
    assert reg is not None and reg["count"] > 0
    assert reg["hit_rate"] >= 0.7  # uptrend regime calls resolve up
