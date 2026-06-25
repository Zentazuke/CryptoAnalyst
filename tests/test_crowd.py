"""Measured funding-crowding contrarian calibration."""
from __future__ import annotations

import numpy as np

from analyst.crowd import calibrate_funding_contrarian

HOUR = 3_600_000
START = 1_700_000_000_000


def _candles(close):
    return [
        {"ts": START + i * HOUR, "open": float(close[i - 1] if i else close[0]),
         "high": float(close[i]) * 1.001, "low": float(close[i]) * 0.999,
         "close": float(close[i]), "volume": 100.0}
        for i in range(len(close))
    ]


def test_returns_none_without_funding():
    assert calibrate_funding_contrarian(_candles(np.full(400, 100.0)), [], horizon=24) is None


def test_perfectly_contrarian_funding_scores_high():
    # Construct: when funding is high, price falls over the next H; when low, it rises.
    n, H = 500, 12
    rng = np.random.default_rng(0)
    close = np.full(n, 100.0)
    funding = []
    for i in range(n):
        f = 0.001 if (i // 25) % 2 == 0 else -0.001  # alternating crowded long / short blocks
        funding.append({"t": START + i * HOUR, "v": f})
    # make the next-H move oppose the crowd (contrarian holds)
    for i in range(n):
        drift = -0.002 if funding[i]["v"] > 0 else 0.002
        if i + 1 < n:
            close[i + 1] = close[i] * (1 + drift)
    rep = calibrate_funding_contrarian(_candles(close), funding, horizon=H, window=50)
    assert rep is not None and rep["count"] > 0
    assert rep["hit_rate"] >= 0.8           # contrarian held strongly
    assert rep["lift"] is not None and rep["lift"] > 1.2


def test_report_shape():
    n = 400
    close = 100.0 + np.cumsum(np.random.default_rng(1).normal(0, 0.3, n))
    funding = [{"t": START + i * HOUR, "v": float(np.random.default_rng(i).normal(0, 0.0005))} for i in range(n)]
    rep = calibrate_funding_contrarian(_candles(close), funding, horizon=24, window=100)
    assert rep is None or {"hit_rate", "base_rate", "lift", "count", "span_days"} <= set(rep)
