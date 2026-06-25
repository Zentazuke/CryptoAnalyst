"""Collect microstructure snapshots from the CLI.

Run once, or on a schedule (e.g. Windows Task Scheduler / a loop) to build a
time series of spread, depth, OI, funding, and basis.

    python -m analyst.collect_micro --symbols BTC_USDT,ETH_USDT
"""
from __future__ import annotations

import argparse

from analyst.config import DB_PATH, DEFAULT_SYMBOLS, DEPTH_BAND_BPS
from analyst.ingestion import make_source
from analyst.microstructure import collect_microstructure
from analyst.storage import Store
from analyst.utils import ms_to_iso


def run(symbols: list[str], db_path, band_bps: float, book_depth: int) -> None:
    source = make_source()
    try:
        with Store(db_path) as store:
            for symbol in symbols:
                snap = collect_microstructure(
                    symbol, source, store, band_bps=band_bps, book_depth=book_depth
                )
                fund = f"{snap.funding_rate:+.6f}" if snap.funding_rate is not None else "n/a"
                basis = f"{snap.basis_bps:+.2f}bps" if snap.basis_bps is not None else "n/a"
                oi = f"{snap.open_interest:,.1f}" if snap.open_interest is not None else "n/a"
                print(
                    f"  {symbol:<10} {ms_to_iso(snap.ts)}  spread={snap.spread_bps:.2f}bps  "
                    f"depth(bid/ask quote)={snap.bid_depth_quote:,.0f}/{snap.ask_depth_quote:,.0f}  "
                    f"OI={oi}  funding={fund}  basis={basis}"
                )
    finally:
        source.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect microstructure snapshots.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--band-bps", type=float, default=DEPTH_BAND_BPS)
    parser.add_argument("--book-depth", type=int, default=50)
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    print(f"=== MICROSTRUCTURE {symbols} band={args.band_bps}bps -> {args.db} ===")
    run(symbols, args.db, args.band_bps, args.book_depth)
    print("done.")


if __name__ == "__main__":
    main()
