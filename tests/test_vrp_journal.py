"""Tests for the VRP signal journal (temp DB, no network)."""
import tempfile
from pathlib import Path

from analyst.storage.vrp_journal import VrpJournal


def _read(verdict="rich", prem=9.0):
    return {"currency": "BTC", "implied_vol_dvol": 55.0, "realized_vol_30d": 46.0,
            "premium_volpts": prem, "premium_percentile": 0.8, "verdict": verdict}


def _journal():
    d = tempfile.mkdtemp()
    return VrpJournal(path=str(Path(d) / "vrp.duckdb"))


def test_record_and_recent():
    j = _journal()
    assert j.record(_read()) is True
    rows = j.recent()
    assert len(rows) == 1
    assert rows[0]["currency"] == "BTC" and rows[0]["verdict"] == "rich"
    assert rows[0]["premium"] == 9.0


def test_dedup_within_window():
    j = _journal()
    assert j.record(_read()) is True
    assert j.record(_read(prem=8.0)) is False  # same currency, within dedup window
    assert len(j.recent()) == 1


def test_record_rejects_incomplete():
    j = _journal()
    assert j.record({"currency": "BTC"}) is False  # no premium
    assert j.record({"premium_volpts": 5.0}) is False  # no currency


def test_recent_filters_by_currency():
    j = _journal()
    j.record(_read())
    j.conn.execute("INSERT INTO vrp_journal VALUES (?,?,?,?,?,?,?)",
                   [1, "ETH", 60.0, 50.0, 10.0, 0.7, "rich"])
    assert len(j.recent(currency="ETH")) == 1
    assert len(j.recent(currency="BTC")) == 1
    assert len(j.recent()) == 2
