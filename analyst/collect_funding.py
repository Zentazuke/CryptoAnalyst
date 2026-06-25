"""Ingest hourly funding-rate history for the mapped perpetuals.

    python -m analyst.collect_funding --symbols BTC_USDT,ETH_USDT --count 5000
"""
from __future__ import annotations

import argparse

from analyst.config import DB_PATH, DEFAULT_SYMBOLS
from analyst.ingestion import make_source
from analyst.storage import Store
from analyst.utils import ms_to_iso


def run(symbols: list[str], count: int, db_path) -> None:
    source = make_source()
    try:
        with Store(db_path) as store:
            for symbol in symbols:
                perp = source.perp_for(symbol)
                if not perp:
                    print(f"  {symbol:<10} no perp mapping — skipped")
                    continue
                rows, _ = source.fetch_funding_history(perp, total=count)
                n = store.upsert_funding(symbol, rows, source.name)
                span = f"{ms_to_iso(rows[0]['t'])} -> {ms_to_iso(rows[-1]['t'])}" if rows else "n/a"
                print(f"  {symbol:<10} ({perp})  rows={n:<5} {span}")
    finally:
        source.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest funding-rate history.")
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    ap.add_argument("--count", type=int, default=5000)
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    print(f"=== FUNDING HISTORY {symbols} count={args.count} -> {args.db} ===")
    run(symbols, args.count, args.db)
    print("done.")


if __name__ == "__main__":
    main()
