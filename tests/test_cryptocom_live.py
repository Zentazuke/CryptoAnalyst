"""Opt-in live smoke test against the real Crypto.com API.

Skipped by default so the suite stays offline/deterministic. Enable with:
    ANALYST_LIVE=1 python -m pytest tests/test_cryptocom_live.py
"""
from __future__ import annotations

import os

import pytest

from analyst.ingestion.cryptocom import CryptoComSource

pytestmark = pytest.mark.skipif(
    os.environ.get("ANALYST_LIVE") != "1",
    reason="set ANALYST_LIVE=1 to run live API smoke tests",
)


def test_fetch_btc_1h():
    with CryptoComSource() as source:
        candles, raw = source.fetch_ohlcv("BTC_USDT", "1h", count=10)
    assert raw.get("code") in (0, "0")
    assert len(candles) == 10
    c = candles[-1]
    assert c.source == "crypto.com"
    assert c.high >= c.low > 0
    # ascending order
    assert all(a.ts < b.ts for a, b in zip(candles, candles[1:]))
