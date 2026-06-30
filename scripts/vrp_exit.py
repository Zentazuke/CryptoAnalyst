"""Step 4: does structurally capping the short-vol tail help?

Compares hold-to-expiry vs defined-risk caps and dynamic stop-losses, swept over
levels, for BTC/ETH. The question: do these turn the catastrophic months into
bounded losses and lift the risk-adjusted return — or does the insurance/whipsaw
cost eat the premium?

    python -m scripts.vrp_exit --horizon 30 --cost 2
"""
from __future__ import annotations

import argparse
from functools import partial

import numpy as np

from analyst.ingestion.binance import BinanceSource
from analyst.ingestion.deribit import DeribitSource
from analyst.vol_exit import (
    run_vrp_exit, hold_to_expiry_pnl, defined_risk_pnl, dynamic_exit_pnl,
)


def _load(sym, cur, bs, ds):
    cndl, _ = bs.fetch_ohlcv_history(sym, "1D", 2000)
    day_index = np.array([c.ts // 86_400_000 for c in cndl], np.int64)
    closes = np.array([c.close for c in cndl], float)
    dvh = ds.fetch_dvol_history(cur, days=2000, resolution=86400)
    return day_index, closes, {r["ts"] // 86_400_000: r["dvol"] for r in dvh}


def _row(label, m):
    if not m:
        return f"  {label:<26} (n/a)"
    return (f"  {label:<26} Sharpe {m['ann_sharpe']:+.2f}  mean {m['mean_pnl_volpts']:+.1f}  "
            f"hit {m['hit_rate']*100:.0f}%  maxDD {m['max_drawdown_volpts']:+.0f}  worst {m['worst_trade_volpts']:+.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--cost", type=float, default=2.0)
    args = ap.parse_args()
    bs, ds = BinanceSource(), DeribitSource()
    print(f"=== Step 4: structural tail-capping  horizon={args.horizon}d cost={args.cost} ===")
    for sym, cur in (("BTC_USDT", "BTC"), ("ETH_USDT", "ETH")):
        di, cl, dvol = _load(sym, cur, bs, ds)
        run = lambda fn: run_vrp_exit(dvol, di, cl, args.horizon, args.cost, fn)
        print(f"\n--- {sym} ---")
        print(_row("hold-to-expiry (base)", run(hold_to_expiry_pnl)))
        for cap in (25, 15, 10):
            m = run(partial(defined_risk_pnl, max_loss=cap, hedge_cost=1.5))
            print(_row(f"defined-risk cap -{cap} (h1.5)", m))
        for stop in (20, 12, 8):
            m = run(partial(dynamic_exit_pnl, stop_loss=stop, min_days=5, exit_cost=1.0))
            print(_row(f"dynamic stop -{stop}", m))
    bs.close(); ds.close()
    print("\ndone.")


if __name__ == "__main__":
    main()
