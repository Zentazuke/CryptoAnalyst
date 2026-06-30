"""export_lean.py — dump the analyst's CAUSAL daily lean + regime over history.

This is the bridge for the intraday-TSM integration. For each historical day it
replays the analyst's OWN functions on the candles available up to that day:

  * ensemble_read(slice)  -> calibrated directional lean (weights learned only from
                             that slice's resolved history — causal by construction)
  * classify_latest(slice) -> regime label + confidence as of that day

Because we re-run the analyst's real functions on an expanding window, there is no
lookahead: the row for day d uses only candles up to d. The output is a tidy CSV the
Trading Bot's intraday backtest reads (and lags by one day, so the 08:00 decision only
ever sees the prior completed daily bar).

    python -m scripts.export_lean --symbols BTC_USDT,ETH_USDT --timeframe 1d --days 1900
    # writes analyst_lean.csv  (copy it into ../Trading Bot/data_cache/)
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

# run-from-anywhere: put the repo root (parent of scripts/) on the path so `analyst`
# imports work even when this file is launched by path and isn't pip-installed.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyst.ensemble import ensemble_read
from analyst.ingestion import make_source
from analyst.regime import classify_series


def _day(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def fetch_rows(source, symbol: str, timeframe: str, count: int) -> list[dict]:
    """Deep history as the dict candles the analyst functions expect."""
    hist = getattr(source, "fetch_ohlcv_history", None)
    if callable(hist):
        candles, _ = hist(symbol, timeframe, count)
    else:
        candles, _ = source.fetch_ohlcv(symbol, timeframe, count=min(count, 1000))
    return [{"ts": c.ts, "open": c.open, "high": c.high, "low": c.low,
             "close": c.close, "volume": c.volume} for c in candles]


def export_symbol(source, symbol: str, timeframe: str, count: int, writer, stride: int,
                  do_ensemble: bool) -> int:
    rows = fetch_rows(source, symbol, timeframe, count)
    rows.sort(key=lambda r: r["ts"])
    n = len(rows)
    print(f"  {symbol} {timeframe}: {n} bars fetched")
    # Regime labels: classify_series is causal per-bar (value at i uses only data <= i) and
    # is computed ONCE over the whole series -> fast, so 4h / deep history is practical.
    try:
        regs = classify_series(rows)
    except Exception as exc:  # noqa: BLE001
        print(f"    classify_series failed ({str(exc)[:50]}); labels=unknown"); regs = None
    written = 0
    for i in range(250, n, stride):
        lean, score, norm = "neutral", 0.0, 0.0
        if do_ensemble:  # the slow part: causal walk-forward weights, re-learned each bar
            try:
                read = ensemble_read(rows[: i + 1], timeframe)
                if read is not None:
                    lean, score, norm = read["lean"], read["score"], read["normalized"]
            except Exception:  # noqa: BLE001 — never abort the whole export on one bar
                pass
        if regs is not None and i < len(regs):
            label, conf = regs[i].label, round(float(regs[i].confidence), 3)
        else:
            label, conf = "unknown", 0.0
        writer.writerow([_day(rows[i]["ts"]), int(rows[i]["ts"]), symbol, timeframe,
                         f"{rows[i]['close']:.6f}", lean, f"{score:.4f}", f"{norm:.4f}",
                         label, conf])
        written += 1
        if written % 500 == 0:
            print(f"    {symbol}: {written} rows ... (at {_day(rows[i]['ts'])})")
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Export the analyst's causal daily lean+regime")
    ap.add_argument("--symbols", default="BTC_USDT,ETH_USDT")
    ap.add_argument("--timeframe", default="1D")   # analyst uses capital-D daily
    ap.add_argument("--days", type=int, default=1900, help="bars of history to fetch")
    ap.add_argument("--stride", type=int, default=1, help="emit every Nth bar (speed knob)")
    ap.add_argument("--no-ensemble", action="store_true",
                    help="skip the slow ensemble lean; export regime labels only (fast — use for 4h)")
    ap.add_argument("--out", default="analyst_lean.csv")
    args = ap.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    source = make_source()
    print(f"=== EXPORT analyst lean — {symbols} tf={args.timeframe} ~{args.days} bars "
          f"{'(regime labels only)' if args.no_ensemble else '(lean + regime)'} ===")
    total = 0
    try:
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "ts", "symbol", "timeframe", "close", "lean", "score",
                        "normalized", "regime", "confidence"])
            for sym in symbols:
                total += export_symbol(source, sym, args.timeframe, args.days, w, args.stride,
                                       not args.no_ensemble)
    finally:
        if hasattr(source, "close"):
            source.close()
    print(f"\nwrote {args.out} ({total} rows). Copy it into the Trading Bot's data_cache/ and run:")
    print("  python intraday_tsm_analyst.py --days 1825 --gate-symbol BTC_USDT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
