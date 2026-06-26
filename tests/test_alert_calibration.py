"""Alert-type calibration: firing reconstruction + outcome scoring."""
from __future__ import annotations

import numpy as np

from analyst.alert_calibration import aggregate_track_records, calibrate_alerts

HOUR = 3_600_000
START = 1_700_000_000_000


def _candles(close):
    return [
        {"ts": START + i * HOUR, "open": float(close[i - 1] if i else close[0]),
         "high": float(close[i]) * 1.003, "low": float(close[i]) * 0.997,
         "close": float(close[i]), "volume": 100.0}
        for i in range(len(close))
    ]


def test_structure_has_all_types():
    rng = np.random.default_rng(0)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, 400)))
    rep = calibrate_alerts(_candles(close), None, horizon=12, lookback=20)
    assert rep is not None
    for t in ("trend-up", "trend-down", "crowded-long", "crowded-short", "rsi-oversold", "rsi-overbought"):
        assert t in rep["per_type"]


def test_uptrend_fires_trend_up_and_resolves_up():
    close = 100.0 * np.exp(np.cumsum(np.full(400, 0.006)))  # constant-% uptrend
    rep = calibrate_alerts(_candles(close), None, horizon=12, lookback=20)
    tu = rep["per_type"]["trend-up"]
    assert tu is not None and tu["count"] > 0
    assert tu["hit_rate"] >= 0.7  # aligned-up setups resolve up in an uptrend


def test_aggregate_combines_counts():
    a = {"per_type": {"trend-up": {"count": 100, "hit_rate": 0.5, "base_rate": 0.4, "lift": 1.25}}}
    b = {"per_type": {"trend-up": {"count": 100, "hit_rate": 0.3, "base_rate": 0.4, "lift": 0.75}}}
    agg = aggregate_track_records([a, b])
    assert agg["trend-up"]["count"] == 200
    assert abs(agg["trend-up"]["hit_rate"] - 0.4) < 1e-6
