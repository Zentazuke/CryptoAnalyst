"""Key-level detection: swing pivots, clustering, nearest support/resistance."""
from __future__ import annotations

import numpy as np

from analyst.levels import key_levels, round_levels, swing_pivots

HOUR = 3_600_000
START = 1_700_000_000_000


def _candles(close, high=None, low=None):
    n = len(close)
    high = close * 1.001 if high is None else high
    low = close * 0.999 if low is None else low
    return [
        {"ts": START + i * HOUR, "open": float(close[i - 1] if i else close[0]),
         "high": float(high[i]), "low": float(low[i]), "close": float(close[i]), "volume": 100.0}
        for i in range(n)
    ]


def test_round_levels_bracket_price():
    lo, hi = round_levels(61234.0)
    assert lo <= 61234.0 <= hi
    assert hi - lo == 1000.0  # decade/10 step at this magnitude


def test_swing_pivots_finds_obvious_peak():
    # a clean peak at index 10
    x = np.concatenate([np.linspace(100, 120, 11), np.linspace(120, 105, 11)[1:]])
    highs, lows = swing_pivots(x, x, k=3)
    assert any(abs(h - 120.0) < 1e-6 for h in highs)


def test_key_levels_split_around_price():
    rng = np.random.default_rng(0)
    close = 100.0 + np.cumsum(rng.normal(0, 0.5, 300))
    res = key_levels(_candles(close))
    price = res["price"]
    assert all(s["price"] < price for s in res["support"])
    assert all(r["price"] > price for r in res["resistance"])
    if res["nearest_support"]:
        assert res["nearest_support"]["dist_pct"] < 0
    if res["nearest_resistance"]:
        assert res["nearest_resistance"]["dist_pct"] > 0


def test_levels_carry_distance_in_atr():
    rng = np.random.default_rng(1)
    close = 100.0 + np.cumsum(rng.normal(0, 0.5, 300))
    res = key_levels(_candles(close))
    for lv in res["levels"]:
        assert "dist_atr" in lv and "dist_pct" in lv and "types" in lv
