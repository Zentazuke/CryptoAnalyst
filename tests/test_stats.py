"""Tests for the honest-uncertainty helpers."""
import math

from analyst.stats import wilson_interval, evidence


def test_wilson_interval_bounds_and_width():
    lo, hi = wilson_interval(50, 100)
    assert 0.0 <= lo < 0.5 < hi <= 1.0
    # more samples -> tighter interval around the same proportion
    lo2, hi2 = wilson_interval(500, 1000)
    assert (hi2 - lo2) < (hi - lo)


def test_wilson_handles_degenerate():
    assert wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = wilson_interval(0, 20)  # all misses: low pinned at 0, high > 0
    assert lo == 0.0 and hi > 0.0


def test_evidence_flags_insufficient_sample():
    e = evidence(hits=9, n=13, base_rate=0.5)
    assert e["verdict"] == "insufficient"
    assert e["significant"] is False
    assert e["n"] == 13


def test_evidence_detects_real_edge():
    # 200/300 = 66.7% vs 50% base on a big sample -> CI excludes base -> edge
    e = evidence(hits=200, n=300, base_rate=0.5)
    assert e["verdict"] == "edge"
    assert e["significant"] is True
    assert e["ci_low"] > 0.5
    assert e["lift"] > 1.0 and e["lift_ci_low"] > 1.0


def test_evidence_no_edge_when_ci_straddles_base():
    # 53/100 vs 50% base -> not distinguishable
    e = evidence(hits=53, n=100, base_rate=0.5)
    assert e["verdict"] == "no-edge"
    assert e["ci_low"] < 0.5 < e["ci_high"]


def test_evidence_detects_negative_edge():
    # 30/100 = 30% vs 50% base, big enough -> significantly worse
    e = evidence(hits=30, n=100, base_rate=0.5)
    assert e["verdict"] == "negative"
    assert e["significant"] is True
    assert e["ci_high"] < 0.5


def test_evidence_no_data():
    e = evidence(hits=0, n=0, base_rate=0.5)
    assert e["verdict"] == "no-data" and e["hit_rate"] is None


def test_p_value_small_for_strong_edge():
    e = evidence(hits=200, n=300, base_rate=0.5)
    assert e["p_value"] is not None and e["p_value"] < 0.01
