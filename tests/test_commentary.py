"""Commentary engine: structure, determinism, and honest framing."""
from __future__ import annotations

import numpy as np

from analyst.commentary import generate_commentary

HOUR_MS = 3_600_000
START = 1_700_000_000_000


def _candles(close):
    out = []
    for i in range(len(close)):
        o = close[i - 1] if i else close[0]
        out.append({
            "ts": START + i * HOUR_MS, "open": float(o),
            "high": float(max(o, close[i]) * 1.002), "low": float(min(o, close[i]) * 0.998),
            "close": float(close[i]), "volume": 100.0,
        })
    return out


def test_structure_and_sections():
    note = generate_commentary(_candles(100.0 + np.cumsum(np.random.default_rng(0).normal(0, 0.3, 200))), "1h")
    assert set(note) >= {"headline", "whats_happening", "what_it_means", "outlook", "caveat"}
    assert note["whats_happening"] and note["headline"]
    assert note["outlook"]["bias"] in ("bullish", "bearish", "neutral", "directional", "high-risk")
    assert note["caveat"]  # honesty caveat always present


def test_uptrend_reads_bullish():
    note = generate_commentary(_candles(100.0 * (1.0 + np.linspace(0, 0.8, 200))), "1h")
    assert note["outlook"]["bias"] == "bullish"
    assert "higher" in note["outlook"]["text"]


def test_deterministic():
    candles = _candles(100.0 + np.cumsum(np.random.default_rng(1).normal(0, 0.4, 200)))
    a = generate_commentary(candles, "1h")
    b = generate_commentary(candles, "1h")
    assert a == b  # no randomness in the note


def test_micro_positioning_mentioned():
    candles = _candles(100.0 + np.cumsum(np.random.default_rng(2).normal(0, 0.3, 200)))
    micro = {"funding_rate": -0.0002, "basis_bps": -5.0, "spread_bps": 1.0}
    note = generate_commentary(candles, "1h", micro=micro)
    joined = " ".join(note["whats_happening"] + note["what_it_means"])
    assert "funding" in joined.lower() and "short" in joined.lower()
