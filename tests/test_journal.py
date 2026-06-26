"""Alert journal: record, de-dup, recent."""
from __future__ import annotations

from analyst.storage.journal import AlertJournal


def _alert(symbol="BTC", kind="trend-down", direction="bear", price=60000.0):
    return {"symbol": symbol, "kind": kind, "direction": direction, "severity": 4, "price": price}


def test_record_and_dedup(tmp_path):
    j = AlertJournal(tmp_path / "j.duckdb")
    assert j.record([_alert()], "4h") == 1
    assert j.record([_alert()], "4h") == 0  # same symbol+kind+tf within window -> deduped
    rec = j.recent()
    assert len(rec) == 1 and rec[0]["symbol"] == "BTC" and rec[0]["price_at_fire"] == 60000.0


def test_skips_alerts_without_price(tmp_path):
    j = AlertJournal(tmp_path / "j.duckdb")
    assert j.record([_alert(price=None)], "4h") == 0


def test_distinct_kinds_both_recorded(tmp_path):
    j = AlertJournal(tmp_path / "j.duckdb")
    n = j.record([_alert(kind="trend-down"), _alert(kind="crowded-long", direction="bear")], "4h")
    assert n == 2 and len(j.recent()) == 2
