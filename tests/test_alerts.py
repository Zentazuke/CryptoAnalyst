"""Confluence-ranked alert detection."""
from __future__ import annotations

from analyst.alerts import detect_alerts


def _row(symbol, regime, momentum=0.0, rsi=50, funding=0.0, above_ema=True, adx=20):
    return {"symbol": symbol, "regime": regime, "momentum": momentum, "rsi": rsi,
            "funding": funding, "above_ema": above_ema, "adx": adx}


def test_aligned_uptrend_fires():
    rows = [_row("AAA", "trend_up", momentum=0.12, rsi=60, above_ema=True)]
    a = detect_alerts(rows)
    assert any(x["kind"] == "trend-up" and x["direction"] == "bull" for x in a)


def test_crowded_long_flush_is_bearish_and_boosted():
    rows = [_row("BBB", "trend_up", momentum=0.2, rsi=75, funding=0.0006, above_ema=True)]
    a = detect_alerts(rows)
    cl = [x for x in a if x["kind"] == "crowded-long"]
    assert cl and cl[0]["direction"] == "bear"
    assert cl[0]["severity"] >= 3  # funding + overbought + extended uptrend + boost


def test_crowded_short_squeeze_is_bullish():
    rows = [_row("CCC", "range", momentum=-0.01, rsi=28, funding=-0.0006)]
    a = detect_alerts(rows)
    assert any(x["kind"] == "crowded-short" and x["direction"] == "bull" for x in a)


def test_ranked_by_severity():
    rows = [
        _row("HI", "trend_up", momentum=0.3, rsi=72, funding=0.0008, above_ema=True),
        _row("LO", "range", momentum=0.0, rsi=82),
    ]
    a = detect_alerts(rows)
    assert a[0]["severity"] >= a[-1]["severity"]
