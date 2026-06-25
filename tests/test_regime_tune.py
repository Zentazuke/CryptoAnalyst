"""Structural tests for the walk-forward tuner."""
from __future__ import annotations

import numpy as np

from analyst.regime import tune

HOUR_MS = 3_600_000
START = 1_700_000_000_000


def _candles(n=400, seed=5):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n)))  # mild drift + noise
    out = []
    for i in range(n):
        o = close[i - 1] if i else close[0]
        out.append({
            "ts": START + i * HOUR_MS, "open": float(o),
            "high": float(max(o, close[i]) * 1.003), "low": float(min(o, close[i]) * 0.997),
            "close": float(close[i]), "volume": float(rng.uniform(50, 150)),
        })
    return out


def test_grid_search_returns_sorted_scores():
    candles = _candles()
    grid = {"adx_trend": [22.0, 28.0], "donchian_n": [15, 20]}
    scored = tune.grid_search(candles, grid, {"horizon": 12})
    assert len(scored) == 4
    objs = [s[0] for s in scored]
    assert objs == sorted(objs, reverse=True)  # best first


def test_walk_forward_reports_oos_comparison():
    out = tune.walk_forward(
        _candles(500),
        grid={"adx_trend": [25.0, 28.0], "donchian_n": [20]},
        calib_params={"horizon": 12},
    )
    assert set(out) >= {"best_params", "train_obj", "test_obj", "default_test_obj"}
    assert "adx_trend" in out["best_params"]
