"""Expected-move + risk framing."""
from __future__ import annotations

import numpy as np

from analyst.risk import risk_frame

HOUR = 3_600_000
START = 1_700_000_000_000


def _candles(close):
    return [
        {"ts": START + i * HOUR, "open": float(close[i - 1] if i else close[0]),
         "high": float(close[i]) * 1.004, "low": float(close[i]) * 0.996,
         "close": float(close[i]), "volume": 100.0}
        for i in range(len(close))
    ]


def test_expected_move_and_band():
    rng = np.random.default_rng(0)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, 300)))
    r = risk_frame(_candles(close), horizon=24)
    assert r is not None
    assert r["expected_move_pct"] > 0
    assert r["band_low"] < r["price"] < r["band_high"]
    assert r["atr_pct"] > 0
    assert r["vol_regime"] in ("compressed", "normal", "elevated")


def test_rr_to_levels():
    rng = np.random.default_rng(1)
    close = 100.0 + np.cumsum(rng.normal(0, 0.4, 300))
    levels = {"nearest_resistance": {"price": float(close[-1]) + 5},
              "nearest_support": {"price": float(close[-1]) - 4}}
    r = risk_frame(_candles(close), levels=levels, horizon=24)
    assert r["long"]["rr"] is not None and r["long"]["rr"] > 0
    assert r["short"]["rr"] is not None and r["short"]["rr"] > 0
    assert r["long"]["target"] == levels["nearest_resistance"]["price"]


def test_higher_vol_widens_band():
    base = np.full(300, 100.0)
    calm = risk_frame(_candles(base + np.cumsum(np.random.default_rng(2).normal(0, 0.05, 300))), horizon=24)
    wild = risk_frame(_candles(base + np.cumsum(np.random.default_rng(2).normal(0, 0.8, 300))), horizon=24)
    assert wild["expected_move_pct"] > calm["expected_move_pct"]
