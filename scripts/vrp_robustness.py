"""Robustness / stability of the winning defined-risk VRP harvest.

The decisive test (the one that exposed direction as luck): does the edge hold in
BOTH halves of the sample, on BOTH coins? Plus a horizon sweep, a cost-sensitivity
sweep, Sharpe confidence intervals, and a DVOL-shuffle placebo.

Winner config: sell vol monthly, defined-risk (loss capped, hedge paid each trade).

    python -m scripts.vrp_robustness
"""
from __future__ import annotations

import argparse
import math
from functools import partial

import numpy as np

from analyst.ingestion.binance import BinanceSource
from analyst.ingestion.deribit import DeribitSource
from analyst.vol_exit import run_vrp_exit, defined_risk_pnl

MAX_LOSS, HEDGE = 12.0, 1.5  # the winning defined-risk cap


def winner(max_loss=MAX_LOSS, hedge=HEDGE):
    return partial(defined_risk_pnl, max_loss=max_loss, hedge_cost=hedge)


def sharpe_ci(ann_sharpe, n, horizon):
    if ann_sharpe is None or n < 4:
        return (float("nan"), float("nan"))
    tpy = 365.0 / horizon
    srp = ann_sharpe / math.sqrt(tpy)
    se = math.sqrt((1 + 0.5 * srp * srp) / n) * math.sqrt(tpy)
    return ann_sharpe - 1.96 * se, ann_sharpe + 1.96 * se


def _load(sym, cur, bs, ds):
    cndl, _ = bs.fetch_ohlcv_history(sym, "1D", 2000)
    di = np.array([c.ts // 86_400_000 for c in cndl], np.int64)
    cl = np.array([c.close for c in cndl], float)
    dvh = ds.fetch_dvol_history(cur, days=2000, resolution=86400)
    return di, cl, {r["ts"] // 86_400_000: r["dvol"] for r in dvh}


def _line(label, m, horizon):
    if not m:
        return f"  {label:<26} (too few trades)"
    lo, hi = sharpe_ci(m["ann_sharpe"], m["n_trades"], horizon)
    return (f"  {label:<26} n={m['n_trades']:>3}  Sharpe {m['ann_sharpe']:+.2f} "
            f"[{lo:+.2f},{hi:+.2f}]  mean {m['mean_pnl_volpts']:+.1f}  "
            f"maxDD {m['max_drawdown_volpts']:+.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost", type=float, default=2.0)
    args = ap.parse_args()
    bs, ds = BinanceSource(), DeribitSource()
    print("=== VRP robustness — winning defined-risk config (cap -12, hedge 1.5) ===")
    for sym, cur in (("BTC_USDT", "BTC"), ("ETH_USDT", "ETH")):
        di, cl, dvol = _load(sym, cur, bs, ds)
        n = len(cl)
        print(f"\n################  {sym}  ################")

        print("\n[sub-period stability]  (the acid test — must hold in BOTH halves)")
        mid = n // 2
        print(_line("full period", run_vrp_exit(dvol, di, cl, 30, args.cost, winner()), 30))
        print(_line("first half", run_vrp_exit(dvol, di[:mid], cl[:mid], 30, args.cost, winner()), 30))
        print(_line("second half", run_vrp_exit(dvol, di[mid:], cl[mid:], 30, args.cost, winner()), 30))

        print("\n[horizon sweep]")
        for H in (7, 14, 30):
            print(_line(f"hold {H}d", run_vrp_exit(dvol, di, cl, H, args.cost, winner()), H))

        print("\n[cost sensitivity, 30d]")
        for c in (1, 2, 3, 4):
            print(_line(f"cost {c} vol-pts", run_vrp_exit(dvol, di, cl, 30, c, winner()), 30))

        print("\n[placebo: shuffle DVOL across days, 30d]")
        rng = np.random.default_rng(0)
        days, vals = list(dvol.keys()), list(dvol.values())
        sh = []
        for _ in range(200):
            shuffled = dict(zip(days, rng.permutation(vals)))
            m = run_vrp_exit(shuffled, di, cl, 30, args.cost, winner())
            if m:
                sh.append(m["ann_sharpe"])
        real = run_vrp_exit(dvol, di, cl, 30, args.cost, winner())["ann_sharpe"]
        sh = np.array(sh)
        print(f"  real Sharpe {real:+.2f} beats {float((sh < real).mean())*100:.0f}% of placebos "
              f"(placebo mean {sh.mean():+.2f}, 95th {np.percentile(sh,95):+.2f})")
    bs.close(); ds.close()
    print("\ndone.")


if __name__ == "__main__":
    main()
