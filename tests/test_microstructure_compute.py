"""Golden-vector tests for microstructure math."""
from __future__ import annotations

import math

from analyst.microstructure import compute as mc


def test_mid_and_spread():
    assert mc.mid_price(100.0, 100.10) == 100.05
    # (0.10 / 100.05) * 10_000 = 9.995...
    assert math.isclose(mc.spread_bps(100.0, 100.10), 0.10 / 100.05 * 10_000)


def test_spread_zero_when_locked():
    assert mc.spread_bps(100.0, 100.0) == 0.0


def test_depth_within_band_bids():
    mid = 100.0
    # band 100 bps = 1% -> include bids >= 99.0
    bids = [[99.5, 2.0], [99.0, 3.0], [98.0, 5.0]]  # 98.0 excluded
    base, quote = mc.depth_within_band(bids, mid, 100.0, "bid")
    assert base == 5.0
    assert math.isclose(quote, 99.5 * 2.0 + 99.0 * 3.0)


def test_depth_within_band_asks():
    mid = 100.0
    asks = [[100.5, 1.0], [101.0, 4.0], [102.0, 9.0]]  # 102.0 excluded at 100 bps
    base, quote = mc.depth_within_band(asks, mid, 100.0, "ask")
    assert base == 5.0
    assert math.isclose(quote, 100.5 * 1.0 + 101.0 * 4.0)


def test_basis_bps():
    # mark above index -> positive (contango)
    assert math.isclose(mc.basis_bps(101.0, 100.0), 100.0)
    assert mc.basis_bps(None, 100.0) is None
    assert mc.basis_bps(100.0, 0) is None
