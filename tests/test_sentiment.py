"""SentimentClient bundling + graceful degradation (offline-stubbed)."""
from __future__ import annotations

import httpx

from analyst.ingestion.sentiment import SentimentClient


class StubClient(SentimentClient):
    def __init__(self, responses: dict):
        self.base_url = ""
        self._own = False
        self._client = None
        self._responses = responses

    def _get(self, path):  # type: ignore[override]
        for needle, val in self._responses.items():
            if needle in path:
                if isinstance(val, Exception):
                    raise val
                return val
        raise httpx.HTTPError(f"404 {path}")


def test_key_translation():
    assert SentimentClient._key("BTC_USDT") == "BTC-USDT"


def test_bundle_assembles_when_engine_up():
    sc = StubClient({
        "/outlook/": {"label": "bullish", "outlook_score": 0.4, "confidence": 0.6,
                      "context": {"fear_greed_value": 72}, "positioning": {"signal": "long"},
                      "direction_prob_6h": 0.58},
        "/alerts/": {"shock": "none"},
        "/social/": {"events": [{"text": "x", "score": 0.5}]},
    })
    b = sc.bundle("BTC_USDT")
    assert b is not None
    assert b["outlook"]["label"] == "bullish"
    assert b["context"]["fear_greed_value"] == 72
    assert b["direction_prob_6h"] == 0.58
    assert b["alerts"]["shock"] == "none"


def test_bundle_none_when_engine_down():
    sc = StubClient({"/outlook/": httpx.ConnectError("refused")})
    assert sc.bundle("BTC_USDT") is None


def test_bundle_tolerates_partial_failure():
    sc = StubClient({
        "/outlook/": {"label": "bearish", "context": None},
        "/alerts/": httpx.HTTPError("500"),
        "/social/": httpx.HTTPError("500"),
    })
    b = sc.bundle("BTC_USDT")
    assert b is not None and b["alerts"] is None and b["recent"] is None
