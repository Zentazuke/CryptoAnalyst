"""Tests for the live VRP read (synthetic DVOL source, no network)."""
import numpy as np

from analyst.vrp_live import vrp_read


class FakeDeribit:
    def __init__(self, dvol_by_day):
        self._d = dvol_by_day

    def fetch_dvol_history(self, currency, days=2000, resolution=86400):
        return [{"ts": d * 86_400_000, "dvol": v} for d, v in sorted(self._d.items())]


def _candles(n=400, sigma=0.02, seed=0):
    rng = np.random.default_rng(seed)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, sigma, n)))
    return [{"ts": i * 86_400_000, "close": float(c)} for i, c in enumerate(closes)]


def test_returns_none_without_dvol():
    c = _candles()
    assert vrp_read("BTC", c, source=FakeDeribit({})) is None


def test_rich_premium_when_implied_far_above_realized():
    c = _candles(sigma=0.02)  # realized ~38%
    dvol = {i: 70.0 for i in range(len(c))}  # implied much higher, but spike the last day richer
    dvol[len(c) - 1] = 110.0
    r = vrp_read("BTC", c, source=FakeDeribit(dvol))
    assert r is not None
    assert r["premium_volpts"] > 0
    assert r["verdict"] == "rich"
    assert r["premium_percentile"] >= 0.66


def test_cheap_when_implied_below_realized():
    c = _candles(sigma=0.02)
    dvol = {i: 60.0 for i in range(len(c))}
    dvol[len(c) - 1] = 20.0  # implied collapses below realized on the last day
    r = vrp_read("BTC", c, source=FakeDeribit(dvol))
    assert r["verdict"] == "cheap"
    assert r["premium_percentile"] <= 0.33


def test_read_shape():
    c = _candles()
    dvol = {i: 55.0 + (i % 10) for i in range(len(c))}
    r = vrp_read("ETH", c, source=FakeDeribit(dvol))
    for k in ("implied_vol_dvol", "realized_vol_30d", "premium_volpts",
              "premium_percentile", "verdict", "recommendation", "trade"):
        assert k in r
    assert r["currency"] == "ETH"
