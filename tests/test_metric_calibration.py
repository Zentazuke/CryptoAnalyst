"""metric_calibration: detects a planted edge, rejects noise, handles inversion,
respects causality and staleness."""
from __future__ import annotations

import numpy as np

from analyst.metric_calibration import best_row, evaluate_metric, metric_calls

HOUR_MS = 3_600_000
START = 1_700_000_000_000


def _world(n=2400, seed=7, invert=False, informative=True):
    """Candles whose forward drift follows a slow hidden state, plus a metric
    sampled every 4 bars that (optionally) reads that state."""
    rng = np.random.default_rng(seed)
    state = np.sign(np.sin(np.arange(n) * 2 * np.pi / 400))   # flips every ~200 bars
    rets = 0.004 * state + rng.normal(0, 0.004, n)
    close = 100.0 * np.exp(np.cumsum(rets))
    candles = []
    for i in range(n):
        o = close[i - 1] if i else 100.0
        candles.append({"ts": START + i * HOUR_MS, "open": float(o),
                        "high": float(max(o, close[i]) * 1.001),
                        "low": float(min(o, close[i]) * 0.999),
                        "close": float(close[i]), "volume": 1.0,
                        "symbol": "T", "timeframe": "1h", "source": "t", "ingest_ts": START})
    series = []
    for i in range(0, n, 4):
        if informative:
            v = state[i] + rng.normal(0, 0.2)
            if invert:
                v = -v
        else:
            v = rng.normal(0, 1)
        series.append({"ts": START + i * HOUR_MS, "value": float(v)})
    return candles, series


def test_detects_planted_edge():
    candles, series = _world()
    rep = evaluate_metric("state_reader", series, candles, "1h", horizon=24)
    best = best_row(rep)
    assert best is not None, rep["rows"]
    assert best["orientation"] == "high_bullish"
    assert best["accuracy"] > best["base"]
    assert best["stable"] and best["significant"]


def test_inverted_metric_wins_on_bearish_orientation():
    candles, series = _world(invert=True)
    rep = evaluate_metric("fear_style", series, candles, "1h", horizon=24)
    best = best_row(rep)
    assert best is not None
    assert best["orientation"] == "high_bearish"


def test_noise_is_not_reliable():
    candles, series = _world(informative=False)
    rep = evaluate_metric("random_walkie", series, candles, "1h", horizon=24)
    assert best_row(rep) is None       # nothing to claim
    for r in rep["rows"]:
        assert not (r["significant"] and r["stable"])


def test_causality_no_future_observations():
    """A bar must never see an observation stamped after it."""
    candles, series = _world()
    ts = [c["ts"] for c in candles]
    calls = metric_calls(series, ts, window=10)
    # shift every observation 1 bar into the future: first informative call moves later
    shifted = [{"ts": r["ts"] + HOUR_MS, "value": r["value"]} for r in series]
    calls_s = metric_calls(shifted, ts, window=10)
    first = int(np.argmax(calls != 0))
    first_s = int(np.argmax(calls_s != 0))
    assert first_s >= first + 1


def test_staleness_kills_calls():
    candles, series = _world()
    ts = [c["ts"] for c in candles]
    truncated = series[: len(series) // 2]        # metric feed dies halfway
    calls = metric_calls(truncated, ts, window=10)
    assert np.all(calls[-len(ts) // 3:] == 0)     # late bars: no stale calls


def test_short_series_makes_no_calls():
    candles, series = _world()
    ts = [c["ts"] for c in candles]
    assert np.all(metric_calls(series[:20], ts, window=60) == 0)
