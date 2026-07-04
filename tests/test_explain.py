"""explain_signals: structure, consistency with the raw signals, and honesty rules."""
from __future__ import annotations

from analyst.ensemble import directional_signals
from analyst.explain import explain_signals
from analyst.signal_eval import _combinations


def test_explain_structure(candles):
    rep = explain_signals(candles, "1h")
    assert set(rep) == {"timeframe", "horizon", "fired", "summary"}
    assert rep["timeframe"] == "1h"
    assert rep["horizon"] > 0
    s = rep["summary"]
    assert s["fired_total"] == len(rep["fired"])
    assert s["read"] in ("bullish", "bearish", "mixed", "no-reliable-signal")
    for f in rep["fired"]:
        assert f["direction"] in ("bullish", "bearish")
        assert "verdict" in f and "reliable" in f


def test_fired_matches_latest_bar(candles):
    """Every fired entry must agree with the actual latest-bar signal value,
    and every nonzero latest-bar signal must appear exactly once."""
    sig = directional_signals(candles)
    sig.update(_combinations(sig))
    rep = explain_signals(candles, "1h")
    by_name = {f["signal"]: f for f in rep["fired"]}
    assert len(by_name) == len(rep["fired"])  # no duplicates
    for name, arr in sig.items():
        v = float(arr[-1])
        if v == 0:
            assert name not in by_name
        else:
            assert name in by_name
            want = "bullish" if v > 0 else "bearish"
            assert by_name[name]["direction"] == want


def test_reliable_first_ordering(candles):
    rep = explain_signals(candles, "1h")
    flags = [bool(f["reliable"]) for f in rep["fired"]]
    assert flags == sorted(flags, reverse=True)  # all reliable rows come first


def test_summary_counts_only_reliable(candles):
    rep = explain_signals(candles, "1h")
    rb = sum(1 for f in rep["fired"] if f["reliable"] and f["direction"] == "bullish")
    rbear = sum(1 for f in rep["fired"] if f["reliable"] and f["direction"] == "bearish")
    assert rep["summary"]["reliable_bullish"] == rb
    assert rep["summary"]["reliable_bearish"] == rbear


def test_uncalibrated_never_reliable(candles):
    rep = explain_signals(candles, "1h")
    for f in rep["fired"]:
        if f["verdict"] == "uncalibrated":
            assert f["reliable"] is False and f["significant"] is False
