"""Tests for the probability-reliability harness (synthetic)."""
import numpy as np

from analyst.calibration_reliability import (
    reliability_curve, brier_score, calibration_report, recalibration_skill,
)


def test_brier_perfect_and_worst():
    assert brier_score([1, 0, 1], [1, 0, 1]) == 0.0
    assert brier_score([1, 0], [0, 1]) == 1.0


def test_well_calibrated_has_low_bias():
    rng = np.random.default_rng(0)
    probs = rng.uniform(0, 1, 4000)
    outcomes = (rng.uniform(0, 1, 4000) < probs).astype(float)  # outcome happens with prob p
    rep = calibration_report(probs, outcomes)
    assert abs(rep["calibration_bias"]) < 0.05      # honest by construction
    assert rep["skill_score"] > 0                    # beats predicting the base rate


def test_overconfident_detected():
    rng = np.random.default_rng(1)
    # claims high prob (0.9) but only happens 50% -> overconfident, positive bias
    probs = np.full(500, 0.9)
    outcomes = (rng.uniform(0, 1, 500) < 0.5).astype(float)
    rep = calibration_report(probs, outcomes)
    assert rep["calibration_bias"] > 0.3


def test_reliability_curve_bins():
    probs = np.array([0.05, 0.15, 0.95, 0.96])
    outcomes = np.array([0.0, 0.0, 1.0, 1.0])
    curve = reliability_curve(probs, outcomes, n_bins=10)
    assert all("mean_pred" in b and "observed" in b and b["n"] > 0 for b in curve)


def test_recalibration_skill_helps_a_biased_forecaster():
    rng = np.random.default_rng(2)
    n = 600
    true_p = rng.uniform(0.2, 0.8, n)
    outcomes = (rng.uniform(0, 1, n) < true_p).astype(float)
    # a miscalibrated forecaster: squashes probs toward 0.5
    probs = 0.5 + (true_p - 0.5) * 0.3
    sk = recalibration_skill(probs, outcomes)
    assert sk is not None and sk["improved"]  # isotonic should fix the squash OOS
