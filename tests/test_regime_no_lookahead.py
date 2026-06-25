"""No-look-ahead: classifying a prefix must reproduce past labels exactly.

If appending future bars ever changed an earlier bar's regime call, the
classifier would be using future information — a disqualifying bug.
"""
from __future__ import annotations

import numpy as np

from analyst.regime import classify_series, compute_regime_features

HOUR_MS = 3_600_000
START = 1_700_000_000_000


def _candles(n=260, seed=7):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    out = []
    for i in range(n):
        o = close[i - 1] if i else close[0]
        hi = max(o, close[i]) * (1 + abs(rng.normal(0, 0.003)))
        lo = min(o, close[i]) * (1 - abs(rng.normal(0, 0.003)))
        out.append({
            "ts": START + i * HOUR_MS, "open": float(o), "high": float(hi),
            "low": float(lo), "close": float(close[i]), "volume": float(rng.uniform(50, 150)),
        })
    return out


def test_labels_are_prefix_stable():
    candles = _candles()
    full = [r.label for r in classify_series(candles)]
    for k in (len(candles) // 2, len(candles) - 30, len(candles) - 1):
        partial = [r.label for r in classify_series(candles[:k])]
        assert partial == full[:k], f"labels changed at cut {k}"


def test_features_are_prefix_stable():
    candles = _candles()
    full = compute_regime_features(candles)
    k = len(candles) - 20
    partial = compute_regime_features(candles[:k])
    for name, arr in partial.items():
        head = full[name][:k]
        mask = np.isfinite(head) & np.isfinite(arr)
        assert np.array_equal(np.isfinite(head), np.isfinite(arr)), f"{name} finiteness changed"
        np.testing.assert_allclose(arr[mask], head[mask], rtol=1e-12, atol=1e-12)
