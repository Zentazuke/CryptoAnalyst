"""Structural + sanity tests for the ML regime model."""
from __future__ import annotations

import numpy as np

from analyst.regime import model as M

HOUR_MS = 3_600_000
START = 1_700_000_000_000


def _candles(n=900, seed=11):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.012, n)))
    out = []
    for i in range(n):
        o = close[i - 1] if i else close[0]
        out.append({
            "ts": START + i * HOUR_MS, "open": float(o),
            "high": float(max(o, close[i]) * (1 + abs(rng.normal(0, 0.003)))),
            "low": float(min(o, close[i]) * (1 - abs(rng.normal(0, 0.003)))),
            "close": float(close[i]), "volume": float(rng.uniform(50, 150)),
        })
    return out


def test_build_dataset_shapes_and_labels():
    X, y, idx = M.build_dataset(_candles(), horizon=12, k=1.0)
    assert X.shape[0] == len(y) == len(idx)
    assert X.shape[1] == len(M.MODEL_FEATURES)
    assert np.all(np.isfinite(X))
    assert set(np.unique(y)).issubset(set(M.CLASSES))
    assert np.all(np.diff(idx) >= 0)  # chronological


def test_walk_forward_eval_structure():
    rep = M.walk_forward_eval(_candles(900), horizon=12, k=1.0, n_splits=4)
    assert 0.0 <= rep["ml_balanced_acc"] <= 1.0
    assert 0.0 <= rep["rule_balanced_acc"] <= 1.0
    assert rep["oos_samples"] > 0
    assert set(rep["ml_recall"]) == set(M.CLASSES)


def test_predict_latest_returns_distribution():
    out = M.train_and_predict_latest(_candles(900), horizon=12, k=1.0)
    assert out is not None
    assert abs(sum(out["probs"].values()) - 1.0) < 1e-6
    assert out["argmax"] in M.CLASSES
