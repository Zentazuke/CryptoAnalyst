"""Collect one microstructure snapshot: fetch -> compute -> archive -> store.

Spot order book yields mid/spread/depth; the mapped perpetual yields open
interest, funding, mark/index, and basis. All raw payloads are archived
together for replay, consistent with the provenance discipline of A0.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from analyst.config import DEPTH_BAND_BPS, RAW_DIR
from analyst.ingestion.archive import archive_raw
from analyst.microstructure.compute import (
    basis_bps,
    depth_within_band,
    mid_price,
    spread_bps,
)
from analyst.models import IngestResult, MicroSnapshot
from analyst.utils import now_ms


def compute_microstructure(
    symbol: str, source: Any, *, book_depth: int = 50, band_bps: float = DEPTH_BAND_BPS,
) -> tuple[MicroSnapshot, dict]:
    """Fetch + compute a microstructure snapshot (no storage). Returns (snap, raws).

    Derivatives (OI, funding, mark/index, basis) come from the mapped perp and
    are left ``None`` if the symbol has no perp or the venue can't serve them.
    """
    book, raw_book = source.fetch_orderbook(symbol, depth=book_depth)
    if not book["bids"] or not book["asks"]:
        raise ValueError(f"empty order book for {symbol}")

    best_bid = book["bids"][0][0]
    best_ask = book["asks"][0][0]
    mid = mid_price(best_bid, best_ask)
    bid_base, bid_quote = depth_within_band(book["bids"], mid, band_bps, "bid")
    ask_base, ask_quote = depth_within_band(book["asks"], mid, band_bps, "ask")

    raws: dict[str, Any] = {"book": raw_book}
    oi = funding = mark = index = basis = None

    perp = source.perp_for(symbol)
    if perp:
        try:
            pticker, raw_pt = source.fetch_ticker(perp)
            oi = pticker.get("oi")
            raws["perp_ticker"] = raw_pt
            mk, raw_mk = source.fetch_valuation(perp, "mark_price", 1)
            ix, raw_ix = source.fetch_valuation(perp, "index_price", 1)
            fh, raw_fh = source.fetch_valuation(perp, "funding_hist", 1)
            mark = mk[-1]["v"] if mk else None
            index = ix[-1]["v"] if ix else None
            funding = fh[-1]["v"] if fh else None
            basis = basis_bps(mark, index)
            raws.update({"mark_price": raw_mk, "index_price": raw_ix, "funding_hist": raw_fh})
        except Exception:  # noqa: BLE001 - spot-only coin / no perp data
            pass

    snap = MicroSnapshot(
        symbol=symbol, ts=book["t"], mid=mid, best_bid=best_bid, best_ask=best_ask,
        spread_bps=spread_bps(best_bid, best_ask), depth_band_bps=band_bps,
        bid_depth_base=bid_base, ask_depth_base=ask_base,
        bid_depth_quote=bid_quote, ask_depth_quote=ask_quote,
        open_interest=oi, funding_rate=funding, mark_price=mark, index_price=index,
        basis_bps=basis, source=source.name, ingest_ts=now_ms(),
    )
    return snap, raws


def collect_microstructure(
    symbol: str, source: Any, store: Any, *,
    book_depth: int = 50, band_bps: float = DEPTH_BAND_BPS, raw_dir: Path = RAW_DIR,
) -> MicroSnapshot:
    """Capture, archive, and persist a microstructure snapshot for ``symbol``."""
    snap, raws = compute_microstructure(symbol, source, book_depth=book_depth, band_bps=band_bps)
    raw_path = archive_raw(raws, source.name, symbol, "micro", raw_dir)
    store.upsert_micro(snap)
    store.log_ingest(
        IngestResult(source=source.name, symbol=symbol, timeframe="micro",
                     fetched_ts=snap.ingest_ts, rows=1, raw_path=str(raw_path))
    )
    return snap
