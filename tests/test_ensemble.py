"""Tests for the calibrated directional ensemble."""
import numpy as np

from analyst.ensemble import (
    directional_signals, forward_outcome, learn_weights, ensemble_calls, SIGNAL_NAMES,
)


def _candles(n=400, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.02, n))
    out = []
    for i, c in enumerate(close):
        hi = c * 1.01
        lo = c * 0.99
        out.append({"ts": i * 86400000, "open": c, "high": hi, "low": lo, "close": c, "volume": 1000.0})
    return out


def test_signals_are_causal_and_ternary():
    candles = _candles()
    sig = directional_signals(candles)
    assert set(sig) == set(SIGNAL_NAMES)
    for name, arr in sig.items():
        assert len(arr) == len(candles)
        assert set(np.unique(arr)).issubset({-1.0, 0.0, 1.0}), name


def test_learn_weights_rewards_edge_and_fades_noise():
    n = 600
    up = np.zeros(n, dtype=bool)
    up[::2] = True  # alternating, perfectly known outcome
    eligible = np.ones(n, dtype=bool)
    # a signal that always calls the right direction -> weight ~ +1
    perfect = np.where(up, 1.0, -1.0)
    # a signal that always calls the wrong direction -> weight ~ -1 (ensemble fades it)
    inverted = -perfect
    # a constant useless signal -> ~0 edge
    useless = np.ones(n)
    w = learn_weights({"perfect": perfect, "inverted": inverted, "useless": useless}, up, eligible)
    assert w["perfect"]["weight"] > 0.9
    assert w["inverted"]["weight"] < -0.9
    assert abs(w["useless"]["weight"]) < 0.2


def test_learn_weights_zero_when_too_few_samples():
    n = 50
    up = np.zeros(n, dtype=bool)
    call = np.zeros(n)
    call[:5] = 1.0  # only 5 calls < min_samples
    w = learn_weights({"sparse": call}, up, np.ones(n, dtype=bool), min_samples=20)
    assert w["sparse"]["weight"] == 0.0


def test_ensemble_calls_follow_weighted_vote():
    n = 4
    signals = {
        "a": np.array([1.0, 1.0, -1.0, 0.0]),
        "b": np.array([1.0, -1.0, -1.0, 0.0]),
    }
    weights = {"a": {"weight": 0.5}, "b": {"weight": 0.3}}
    call, score = ensemble_calls(signals, weights)
    # bar0: +0.8 -> up ; bar1: +0.5-0.3=+0.2 -> up ; bar2: -0.8 -> down ; bar3: 0 -> no call
    assert list(call) == [1.0, 1.0, -1.0, 0.0]
    assert score[0] > 0 and score[2] < 0 and score[3] == 0


def test_forward_outcome_shapes_and_validity():
    candles = _candles(n=200)
    up, sig, valid = forward_outcome(candles, horizon=5)
    assert len(up) == len(sig) == len(valid) == 200
    # last `horizon` bars cannot have a resolved outcome
    assert not valid[-1] and not valid[-5]
    assert valid[100]
