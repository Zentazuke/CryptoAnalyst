"""End-to-end microstructure collection with an offline fake source."""
from __future__ import annotations

import math

from analyst.microstructure import collect_microstructure
from analyst.storage import Store

TS = 1_700_000_000_000


class FakeMicroSource:
    name = "fake"

    def perp_for(self, symbol):
        return "FAKE-PERP" if symbol == "BTC_USDT" else None

    def fetch_orderbook(self, symbol, depth=50):
        book = {
            "bids": [[99.5, 2.0], [99.0, 3.0], [98.0, 5.0]],
            "asks": [[100.5, 1.0], [101.0, 4.0], [102.0, 9.0]],
            "t": TS,
        }
        return book, {"code": 0, "result": {"data": [book]}}

    def fetch_ticker(self, symbol):
        return {"instrument": symbol, "oi": 1234.5, "t": TS}, {"code": 0}

    def fetch_valuation(self, symbol, valuation_type, count=1):
        v = {"mark_price": 101.0, "index_price": 100.0, "funding_hist": 0.0001}[valuation_type]
        return [{"t": TS, "v": v}], {"code": 0}


def test_collect_computes_stores_and_archives(tmp_path):
    raw_dir = tmp_path / "raw"
    with Store(tmp_path / "t.duckdb") as store:
        snap = collect_microstructure(
            "BTC_USDT", FakeMicroSource(), store, band_bps=100.0, raw_dir=raw_dir
        )

        # mid 100.0; spread (1.0/100.0)*1e4 = 100 bps
        assert snap.mid == 100.0
        assert math.isclose(snap.spread_bps, 100.0)
        # depth within 100 bps excludes the 98.0 bid and 102.0 ask
        assert snap.bid_depth_base == 5.0
        assert snap.ask_depth_base == 5.0
        # derivatives fields from the mapped perp
        assert snap.open_interest == 1234.5
        assert snap.funding_rate == 0.0001
        assert math.isclose(snap.basis_bps, 100.0)  # (101-100)/100*1e4

        # persisted + raw archived
        rows = store.get_micro("BTC_USDT")
        assert len(rows) == 1 and rows[0]["spread_bps"] == snap.spread_bps
        assert len(list(raw_dir.glob("*.json"))) == 1


def test_micro_upsert_is_idempotent(tmp_path):
    with Store(tmp_path / "t.duckdb") as store:
        src = FakeMicroSource()
        collect_microstructure("BTC_USDT", src, store, band_bps=100.0, raw_dir=tmp_path / "r")
        collect_microstructure("BTC_USDT", src, store, band_bps=100.0, raw_dir=tmp_path / "r")
        assert len(store.get_micro("BTC_USDT", limit=10)) == 1  # same ts -> no dup


def test_symbol_without_perp_has_null_derivatives(tmp_path):
    with Store(tmp_path / "t.duckdb") as store:
        snap = collect_microstructure(
            "DOGE_USDT", FakeMicroSource(), store, band_bps=100.0, raw_dir=tmp_path / "r"
        )
        assert snap.open_interest is None
        assert snap.basis_bps is None
