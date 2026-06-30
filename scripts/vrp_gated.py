"""Does the analyst's risk-state gate improve the VRP harvest?

Compares selling vol unconditionally vs only when the analyst says it's safe.
The analyst's measured contribution is the gap: lower drawdown, higher Sharpe,
for giving up the dangerous trades.

    python -m scripts.vrp_gated --horizon 30 --cost 2
"""
from __future__ import annotations

import argparse

import numpy as np

from analyst.ingestion.binance import BinanceSource
from analyst.ingestion.deribit import DeribitSource
from analyst.risk_gate import vol_sell_gate
from analyst.vrp_backtest import run_vrp


def _load(sym, cur, bs, ds):
    cndl, _ = bs.fetch_ohlcv_history(sym, "1D", 2000)
    day_index = np.array([c.ts // 86_400_000 for c in cndl], np.int64)
    closes = np.array([c.close for c in cndl], float)
    dvh = ds.fetch_dvol_history(cur, days=2000, resolution=86400)
    return cndl, day_index, closes, {r["ts"] // 86_400_000: r["dvol"] for r in dvh}


def _row(label, m):
    if not m:
        return f"  {label:<22} (too few trades)"
    return (f"  {label:<22} n={m['n_trades']:>3}  mean {m['mean_pnl_volpts']:+.1f}  "
            f"hit {m['hit_rate']*100:.0f}%  Sharpe {m['ann_sharpe']:+.2f}  "
            f"maxDD {m['max_drawdown_volpts']:+.0f}  worst {m['worst_trade_volpts']:+.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--cost", type=float, default=2.0)
    args = ap.parse_args()
    bs, ds = BinanceSource(), DeribitSource()
    print(f"=== Analyst-gated VRP  horizon={args.horizon}d  cost={args.cost} ===")
    for sym, cur in (("BTC_USDT", "BTC"), ("ETH_USDT", "ETH")):
        cndl, day_index, closes, dvol = _load(sym, cur, bs, ds)
        gates = {
            "unconditional": None,
            "vol-accel only": vol_sell_gate(cndl, use_vol_accel=True, use_drawdown=False, use_regime=False),
            "drawdown only": vol_sell_gate(cndl, use_vol_accel=False, use_drawdown=True, use_regime=False),
            "regime only": vol_sell_gate(cndl, use_vol_accel=False, use_drawdown=False, use_regime=True),
            "combined gate": vol_sell_gate(cndl),
        }
        print(f"\n--- {sym} ---")
        base = run_vrp(dvol, day_index, closes, args.horizon, args.cost)
        for label, g in gates.items():
            m = run_vrp(dvol, day_index, closes, args.horizon, args.cost, gate_ok=g)
            print(_row(label, m))
        if base:
            comb = run_vrp(dvol, day_index, closes, args.horizon, args.cost, gate_ok=gates["combined gate"])
            if comb:
                print(f"  -> combined vs unconditional: Sharpe {base['ann_sharpe']:+.2f} -> {comb['ann_sharpe']:+.2f}, "
                      f"maxDD {base['max_drawdown_volpts']:+.0f} -> {comb['max_drawdown_volpts']:+.0f}")
    bs.close(); ds.close()
    print("\ndone.")


if __name__ == "__main__":
    main()
