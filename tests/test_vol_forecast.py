"""Tests for the realized-vol forecaster (synthetic, no network)."""
import numpy as np

from analyst.vol_forecast import (
    daily_rv_from_intraday, har_forecast, forecast_skill, latest_forecast, gk_variance,
)


def _clustering_rv(n=600, seed=0):
    """A vol series with autocorrelation (clusters) — what HAR should exploit."""
    rng = np.random.default_rng(seed)
    logv = np.zeros(n)
    for i in range(1, n):
        logv[i] = 0.95 * logv[i - 1] + rng.normal(0, 0.3)  # persistent log-variance
    return np.exp(logv) * 1e-4


def test_daily_rv_from_intraday_shape():
    # two days of hourly candles -> 2 daily RV points
    candles = []
    px = 100.0
    for h in range(48):
        px *= 1 + (0.001 if h % 2 else -0.001)
        candles.append({"ts": h * 3_600_000, "close": px})
    days, rv = daily_rv_from_intraday(candles)
    assert len(days) == 2 and len(rv) == 2
    assert np.all(rv > 0)


def test_gk_variance_positive():
    candles = [{"open": 100, "high": 102, "low": 99, "close": 101}] * 5
    v = gk_variance(candles)
    assert np.all(v > 0)


def test_har_beats_persistence_on_clustered_vol():
    rv = _clustering_rv()
    skill = forecast_skill(rv, horizon=5)
    assert skill is not None
    # on genuinely autocorrelated vol, HAR should have positive OOS skill...
    assert skill["har_r2_log"] > 0
    # ...and beat the naive persistence baseline
    assert skill["har_beats_persistence"]


def test_har_forecast_returns_oos_arrays():
    rv = _clustering_rv()
    out = har_forecast(rv, horizon=5)
    assert out is not None
    preds, actual, te, beta = out
    assert len(preds) == len(actual) == len(te)
    assert np.all(preds > 0) and len(beta) == 4


def test_latest_forecast_annualizes():
    rv = _clustering_rv()
    f = latest_forecast(rv, horizon=5, timeframe="1D")
    assert f is not None
    assert f["forecast_vol_annual"] > 0
    assert f["forecast_variance"] > 0


def test_insufficient_history_returns_none():
    assert forecast_skill(np.array([1e-4] * 50), horizon=5) is None
    assert latest_forecast(np.array([1e-4] * 50)) is None
