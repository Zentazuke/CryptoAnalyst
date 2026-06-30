"""Run the variance-risk-premium harvest backtest on BTC/ETH.

Sells implied vol (DVOL) against subsequent realized vol, non-overlapping, gross
and net of costs, and reports the honest drawdown/Sharpe. A placebo (DVOL shuffled
across entry days) confirms the edge comes from the implied-vs-realized spread,
not from luck in the entry schedule.

    python -m scripts.vrp_backtest --horizon 30 --cost 2
"""
from __future__ import annotations

import argparse

import numpy as np

from analyst.ingestion.binance import BinanceSource
from analyst.ingestion.deribit import DeribitSource
from analyst.vrp_backtest import run_vrp, build_trades, vrp_metrics


def _load(sym: str, cur: str, bs: BinanceSource, ds: DeribitSource):
    cndl, _ = bs.fetch_ohlcv_history(sym, "1D", 2000)
    day_index = np.array([c.ts // 86_400_000 for c in cndl], np.int64)
    closes = np.array([c.close for c in cndl], float)
    dvh = ds.fetch_dvol_history(cur, days=2000, resolution=86400)
    dvol_by_day = {r["ts"] // 86_400_000: r["dvol"] for r in dvh}
    return day_index, closes, dvol_by_day


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--cost", type=float, default=2.0)
    args = ap.parse_args()

    bs, ds = BinanceSource(), DeribitSource()
    print(f"=== VRP harvest backtest  horizon={args.horizon}d  cost={args.cost} vol-pts/trade ===")
    for sym, cur in (("BTC_USDT", "BTC"), ("ETH_USDT", "ETH")):
        day_index, closes, dvol_by_day = _load(sym, cur, bs, ds)
        gross = run_vrp(dvol_by_day, day_index, closes, args.horizon, cost_vol_pts=0.0)
        net = run_vrp(dvol_by_day, day_index, closes, args.horizon, cost_vol_pts=args.cost)

        # placebo: shuffle DVOL across the days, breaking the implied/realized link
        rng = np.random.default_rng(0)
        days = list(dvol_by_day.keys())
        vals = list(dvol_by_day.values())
        placebo_sharpes = []
        for _ in range(200):
            shuffled = dict(zip(days, rng.permutation(vals)))
            t = build_trades(shuffled, day_index, closes, args.horizon, args.cost)
            m = vrp_metrics(t, args.horizon)
            if m:
                placebo_sharpes.append(m["ann_sharpe"])
        pb = np.array(placebo_sharpes)

        print(f"\n--- {sym} ---")
        for label, m in (("gross", gross), (f"net (cost {args.cost})", net)):
            print(f"  {label:<16} n={m['n_trades']:>3}  mean {m['mean_pnl_volpts']:+.1f} vol-pts/trade  "
                  f"hit {m['hit_rate']*100:.0f}%  Sharpe {m['ann_sharpe']:.2f}  "
                  f"maxDD {m['max_drawdown_volpts']:.0f}  worst {m['worst_trade_volpts']:.0f}")
        if len(pb):
            real = net["ann_sharpe"]
            pctl = float((pb < real).mean())
            print(f"  placebo Sharpe: mean {pb.mean():+.2f}, 95th pct {np.percentile(pb,95):+.2f}; "
                  f"real net Sharpe {real:+.2f} beats {pctl*100:.0f}% of placebos")
    bs.close(); ds.close()
    print("\ndone.")


if __name__ == "__main__":
    main()
