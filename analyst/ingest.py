"""Ingestion orchestrator + CLI.

Pipeline per symbol:  fetch -> archive raw -> upsert -> gap-check -> log.

Run:
    python -m analyst.ingest --symbols BTC_USDT,ETH_USDT --timeframe 1h --count 300
"""
from __future__ import annotations

import argparse
from pathlib import Path

from analyst.config import (
    DB_PATH,
    DEFAULT_SYMBOLS,
    DEFAULT_TIMEFRAME,
    RAW_DIR,
)
from analyst.ingestion.archive import archive_raw
from analyst.ingestion import make_source
from analyst.ingestion.base import DataSource
from analyst.models import GapReport, IngestResult
from analyst.quality import detect_gaps
from analyst.storage import Store
from analyst.utils import ms_to_iso, now_ms


def ingest_symbol(
    symbol: str,
    timeframe: str,
    count: int,
    store: Store,
    source: DataSource,
    raw_dir: Path = RAW_DIR,
) -> tuple[IngestResult, GapReport]:
    """Run the full pipeline for one symbol and return (provenance, gap report).

    Counts above ~300 paginate backwards (the API caps a single request), when
    the source supports it.
    """
    history = getattr(source, "fetch_ohlcv_history", None)
    if count > 300 and callable(history):
        candles, raws = history(symbol, timeframe, count)
        raw: dict = {"pages": raws}
    else:
        candles, raw = source.fetch_ohlcv(symbol, timeframe, count)
    raw_path = archive_raw(raw, source.name, symbol, timeframe, raw_dir)
    rows = store.upsert_candles(candles)

    result = IngestResult(
        source=source.name,
        symbol=symbol,
        timeframe=timeframe,
        fetched_ts=now_ms(),
        rows=rows,
        raw_path=str(raw_path),
    )
    store.log_ingest(result)

    gap = detect_gaps(candles, timeframe)
    store.record_gap_check(source.name, gap)
    return result, gap


def run(symbols: list[str], timeframe: str, count: int, db_path: str | Path) -> None:
    source = make_source()
    try:
        with Store(db_path) as store:
            for symbol in symbols:
                result, gap = ingest_symbol(symbol, timeframe, count, store, source)
                status = "OK" if not gap.has_gaps else f"GAPS({len(gap.missing)})"
                latest = store.get_candles(symbol, timeframe, limit=1)
                latest_iso = ms_to_iso(latest[0]["ts"]) if latest else "n/a"
                print(
                    f"  {symbol:<10} {timeframe:<4} rows={result.rows:<4} "
                    f"latest={latest_iso}  quality={status}"
                )
    finally:
        source.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest OHLCV into the analyst store.")
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="comma-separated instrument names, e.g. BTC_USDT,ETH_USDT",
    )
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    print(f"=== INGEST {symbols} tf={args.timeframe} count={args.count} -> {args.db} ===")
    run(symbols, args.timeframe, args.count, args.db)
    print("done.")


if __name__ == "__main__":
    main()
