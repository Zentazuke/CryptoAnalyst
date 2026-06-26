"""Implied-vs-realized volatility context (stubbed Deribit)."""
from __future__ import annotations

import numpy as np

from analyst.vol import implied_vol_context


class StubDeribit:
    def __init__(self, dvol):
        self._dvol = dvol

    def fetch_dvol(self, currency):
        return self._dvol


def _candles(close):
    return [{"close": float(c)} for c in close]


def test_premium_when_implied_above_realized():
    close = 100.0 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 0.005, 200)))  # calm realized
    ctx = implied_vol_context("BTC_USDT", _candles(close), "1h", source=StubDeribit(120.0))
    assert ctx is not None and ctx["signal"] == "premium"
    assert ctx["premium_pts"] > 0


def test_discount_when_implied_below_realized():
    close = 100.0 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.03, 200)))  # wild realized
    ctx = implied_vol_context("BTC_USDT", _candles(close), "1h", source=StubDeribit(20.0))
    assert ctx["signal"] == "discount"


def test_none_when_no_dvol():
    close = 100.0 + np.cumsum(np.random.default_rng(2).normal(0, 0.3, 200))
    assert implied_vol_context("XYZ_USDT", _candles(close), "1h", source=StubDeribit(None)) is None
