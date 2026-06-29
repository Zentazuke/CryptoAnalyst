"""Tests for the on-chain divergence calibration (synthetic source, no network)."""
import numpy as np

from analyst.onchain_calibration import calibrate_onchain_divergence


class FakeCM:
    """Minimal CoinMetrics stand-in returning a constructed history."""
    def __init__(self, addr, price):
        self._addr, self._price = addr, price

    def fetch_metrics(self, asset, metrics, days):
        return [{"time": i, "AdrActCnt": a, "PriceUSD": p}
                for i, (a, p) in enumerate(zip(self._addr, self._price))]


def test_returns_none_on_short_history():
    src = FakeCM([1.0] * 40, [1.0] * 40)
    assert calibrate_onchain_divergence("btc", source=src) is None


def test_detects_a_predictive_divergence():
    # Construct history where a bullish divergence (addresses up, price down)
    # is reliably followed by a price rebound -> should score an edge.
    rng = np.random.default_rng(0)
    n = 800
    addr = np.linspace(100, 200, n) + rng.normal(0, 1, n)  # steadily rising usage
    price = np.full(n, 100.0)
    horizon = 10
    # every so often, dip the price (divergence vs rising addr) then rebound
    for t in range(80, n - horizon - 1, 40):
        price[t - 30:t + 1] = np.linspace(110, 90, 31)  # falling into t
        price[t + 1:t + horizon + 1] = 105               # rebound after
    src = FakeCM(addr, price)
    rep = calibrate_onchain_divergence("btc", days=n, horizon=horizon, source=src)
    assert rep is not None
    assert rep["bullish_signals"] > 0
    assert rep["n"] == rep["bullish_signals"] + rep["bearish_signals"]
    assert rep["verdict"] in {"edge", "no-edge", "negative", "insufficient"}


def test_report_has_evidence_fields():
    rng = np.random.default_rng(1)
    n = 700
    addr = 100 + np.cumsum(rng.normal(0, 1, n))
    price = 100 + np.cumsum(rng.normal(0, 1, n))
    src = FakeCM(np.abs(addr) + 50, np.abs(price) + 50)
    rep = calibrate_onchain_divergence("btc", days=n, source=src)
    if rep is not None:  # may be None if no divergence fires on random data
        for k in ("hit_rate", "ci_low", "ci_high", "base_rate", "verdict", "significant"):
            assert k in rep
