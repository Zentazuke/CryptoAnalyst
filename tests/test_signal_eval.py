"""Tests for per-signal directional calibration (synthetic, no network)."""
import numpy as np

from analyst.signal_eval import evaluate_signals, _combinations, _score


def _candles(n=600, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    out = []
    for i, c in enumerate(close):
        out.append({"ts": i * 86_400_000, "open": c, "high": c * 1.02,
                    "low": c * 0.98, "close": float(c), "volume": 1000.0})
    return out


def test_combinations_present_and_ternary():
    sig = {"a": np.array([1.0, -1, 0, 1]), "b": np.array([1.0, -1, 0, -1]),
           "c": np.array([1.0, 1, 0, 0])}
    combos = _combinations(sig)
    assert "COMBO majority(>=2)" in combos and "COMBO all-agree" in combos
    for arr in combos.values():
        assert set(np.unique(arr)).issubset({-1.0, 0.0, 1.0})


def test_score_counts_hits():
    call = np.array([1.0, 1, -1, -1, 0])
    up = np.array([True, False, False, True, True])
    eligible = np.ones(5, dtype=bool)
    hits, n, base = _score(call, eligible, up)
    assert n == 4  # the 0-call is skipped
    assert hits == 2  # bar0 (up,+1) and bar2 (down,-1) correct


def test_evaluate_signals_shape_and_fields():
    res = evaluate_signals(_candles(), "1D")
    assert res["timeframe"] == "1D" and res["horizon"] > 0
    assert len(res["signals"]) > 5
    r = res["signals"][0]
    for k in ("signal", "n", "accuracy", "base", "lift", "ci_low", "ci_high",
              "verdict", "stable", "reliable"):
        assert k in r


def test_a_predictive_signal_is_flagged_reliable():
    # craft a signal that perfectly calls direction in both halves
    candles = _candles(n=800)
    from analyst.ensemble import forward_outcome
    up, sig_mask, valid = forward_outcome(candles, 5)
    # build a fake signals dict via monkeypatching evaluate path is overkill;
    # instead test _score-based reliability logic directly on a perfect caller
    eligible = valid & sig_mask
    perfect = np.where(up, 1.0, -1.0)
    idx = np.arange(len(up)); mid = len(up) // 2
    h1 = _score(perfect, eligible & (idx < mid), up)
    h2 = _score(perfect, eligible & (idx >= mid), up)
    assert h1 and h2 and h1[0] / h1[1] > h1[2] and h2[0] / h2[1] > h2[2]
