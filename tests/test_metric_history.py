"""MetricHistory store: flattening, roundtrip, dedup gap, catalog."""
from __future__ import annotations

from analyst.storage.history import MetricHistory, flatten_numeric

HOUR_MS = 3_600_000
T0 = 1_700_000_000_000


def test_flatten_numeric_shapes():
    src = {
        "score": 0.42, "count": 7, "bull": True, "bear": False,
        "label": "risk-off",              # string -> skipped
        "missing": None,                   # None -> skipped
        "items": [1, 2, 3],                # list -> skipped (no stable key)
        "nested": {"lsr": 1.8, "deep": {"oi": 5e9, "bad": float("nan")}},
    }
    flat = flatten_numeric(src)
    assert flat == {"score": 0.42, "count": 7.0, "bull": 1.0, "bear": 0.0,
                    "nested.lsr": 1.8, "nested.deep.oi": 5e9}


def test_record_and_series_roundtrip(tmp_path):
    h = MetricHistory(path=str(tmp_path / "mh.duckdb"))
    n = h.record("sentiment", "BTC_USDT", {"fear_greed": 61.0, "lsr": 1.4},
                 "test", ts=T0)
    assert n == 2
    h.record("sentiment", "BTC_USDT", {"fear_greed": 55.0}, "test", ts=T0 + HOUR_MS)
    s = h.series("sentiment", "BTC_USDT", "fear_greed")
    assert [r["value"] for r in s] == [61.0, 55.0]
    assert s[0]["ts"] < s[1]["ts"]  # chronological


def test_min_gap_dedup(tmp_path):
    h = MetricHistory(path=str(tmp_path / "mh.duckdb"))
    assert h.record("onchain", "BTC_USDT", {"tx_count": 1.0}, "test",
                    ts=T0, min_gap_s=3600) == 1
    # 10 minutes later, inside the gap -> skipped
    assert h.record("onchain", "BTC_USDT", {"tx_count": 2.0}, "test",
                    ts=T0 + 600_000, min_gap_s=3600) == 0
    # 2 hours later, outside the gap -> recorded
    assert h.record("onchain", "BTC_USDT", {"tx_count": 3.0}, "test",
                    ts=T0 + 2 * HOUR_MS, min_gap_s=3600) == 1
    assert [r["value"] for r in h.series("onchain", "BTC_USDT", "tx_count")] == [1.0, 3.0]


def test_non_numeric_only_writes_nothing(tmp_path):
    h = MetricHistory(path=str(tmp_path / "mh.duckdb"))
    assert h.record("sentiment", "BTC_USDT", {}, "test", ts=T0) == 0
    assert h.series("sentiment", "BTC_USDT", "anything") == []


def test_catalog(tmp_path):
    h = MetricHistory(path=str(tmp_path / "mh.duckdb"))
    h.record("sentiment", "BTC_USDT", {"a": 1.0}, "test", ts=T0)
    h.record("sentiment", "BTC_USDT", {"a": 2.0}, "test", ts=T0 + HOUR_MS)
    h.record("onchain", "ETH_USDT", {"b": 9.0}, "test", ts=T0)
    cat = h.catalog()
    assert {(c["layer"], c["symbol"], c["metric"], c["n"]) for c in cat} == {
        ("sentiment", "BTC_USDT", "a", 2), ("onchain", "ETH_USDT", "b", 1)}
    assert h.catalog(layer="onchain")[0]["metric"] == "b"
    only = h.catalog(layer="sentiment")
    assert len(only) == 1 and only[0]["first_ts"] == T0 and only[0]["last_ts"] == T0 + HOUR_MS
