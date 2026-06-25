"""Calibration sanity: on data engineered to fit a regime, hit-rate is high."""
from __future__ import annotations

import numpy as np

from analyst.regime import calibrate, classify_series
from analyst.regime import classifier as C

HOUR_MS = 3_600_000
START = 1_700_000_000_000


def _candles(close):
    out = []
    for i in range(len(close)):
        o = close[i - 1] if i else close[0]
        out.append({
            "ts": START + i * HOUR_MS, "open": float(o),
            "high": float(max(o, close[i]) * 1.001), "low": float(min(o, close[i]) * 0.999),
            "close": float(close[i]), "volume": 100.0,
        })
    return out


def test_uptrend_trend_up_calls_are_mostly_right():
    close = 100.0 * (1.0 + np.linspace(0, 1.0, 300))  # persistent uptrend
    candles = _candles(close)
    report = calibrate(candles, params={"horizon": 12})
    tu = report["per_label"][C.TREND_UP]
    # with a persistent uptrend, trend_up calls should resolve up most of the time
    assert tu["count"] > 0
    assert tu["hit_rate"] is not None and tu["hit_rate"] >= 0.8


def test_report_structure_and_horizon():
    close = 100.0 + np.cumsum(np.random.default_rng(3).normal(0, 0.4, 200))
    report = calibrate(_candles(close), params={"horizon": 10})
    assert report["horizon"] == 10
    assert report["samples"] > 0
    for lab in (C.RANGE, C.TREND_UP, C.TREND_DOWN, C.BREAKOUT, C.FLASH_RISK, C.LOW_VOL_DRIFT):
        assert lab in report["per_label"]
