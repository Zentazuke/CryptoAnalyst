"""Opt-in live microstructure smoke test against the real Crypto.com API.

    ANALYST_LIVE=1 python -m pytest tests/test_microstructure_live.py
"""
from __future__ import annotations

import os

import pytest

from analyst.ingestion.cryptocom import CryptoComSource
from analyst.microstructure.compute import basis_bps, spread_bps

pytestmark = pytest.mark.skipif(
    os.environ.get("ANALYST_LIVE") != "1",
    reason="set ANALYST_LIVE=1 to run live API smoke tests",
)


def test_live_orderbook_and_perp():
    with CryptoComSource() as s:
        book, _ = s.fetch_orderbook("BTC_USDT", depth=10)
        assert book["bids"] and book["asks"]
        best_bid, best_ask = book["bids"][0][0], book["asks"][0][0]
        assert best_ask >= best_bid > 0
        assert spread_bps(best_bid, best_ask) >= 0

        ticker, _ = s.fetch_ticker("BTCUSD-PERP")
        assert ticker["oi"] and ticker["oi"] > 0

        mark, _ = s.fetch_valuation("BTCUSD-PERP", "mark_price", 1)
        index, _ = s.fetch_valuation("BTCUSD-PERP", "index_price", 1)
        assert basis_bps(mark[-1]["v"], index[-1]["v"]) is not None
