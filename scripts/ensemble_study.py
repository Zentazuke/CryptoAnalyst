"""Walk-forward evaluation of the calibrated directional ensemble.

Learns each signal's weight from its measured edge on the TRAINING window (early
years), then scores the unchanged weights on the TEST window (later years) — so
the result is honest out-of-sample. Compares, on the test set:

  * each single signal,
  * an equal-weight confluence (no learning),
  * the calibrated ensemble (learned weights),

against the majority-class baseline (always guess the dominant direction).

Run:
    python -m scripts.ensemble_study --symbols BTC_USDT,ETH_USDT --timeframe 1D --horizon 5
"""
from __future__ import annotations

import argparse

import numpy as np

from analyst.config import DB_PATH
from analyst.ensemble import (
    directional_signals, forward_outcome, learn_weights, ensemble_calls,
)
from analyst.storage import Store
from scripts.bollinger_study import trailing_squeeze_mask
from analyst.features.engine import compute_indicators


def acc_vs_baseline(call, eligible, up):
    m = eligible & (call != 0)
    n = int(m.sum())
    if n == 0:
        return None
    a = float(np.mean((call[m] > 0) == up[m]))
    ur = float(np.mean(up[m]))
    base = max(ur, 1 - ur)
    return {"n": n, "acc": a, "base": base, "lift": a / base if base else float("nan")}


def run_symbol(store, symbol, timeframe, horizon, train_frac, window, pct):
    candles = store.get_candles(symbol, timeframe)
    n = len(candles)
    if n < 400:
        print(f"  {symbol}: not enough history ({n})"); return
    signals = directional_signals(candles)
    up, significant, valid = forward_outcome(candles, horizon)
    idx = np.arange(n)
    split = int(n * train_frac)

    # train outcomes must resolve before the split (no peeking into test)
    train_elig = valid & significant & (idx < split - horizon)
    test_elig = valid & significant & (idx >= split)

    weights = learn_weights(signals, up, train_elig)
    ens_call, _ = ensemble_calls(signals, weights)

    # equal-weight confluence (no learning): net of all signals, call if |net|>=2
    net = np.sum([signals[k] for k in signals], axis=0)
    conf = np.zeros(n)
    conf[net >= 2] = 1.0
    conf[net <= -2] = -1.0

    print(f"\n================  {symbol}  {timeframe}  ================")
    print(f"bars={n}  train<{split} ({train_frac:.0%})  test>={split}  horizon={horizon}")
    print("\nLEARNED WEIGHTS (from training years)")
    print(f"  {'signal':<16}{'weight':>8}{'train_acc':>11}{'train_n':>9}")
    for k in signals:
        w = weights[k]
        ta = f"{w['train_acc']*100:.1f}%" if w["train_acc"] is not None else "—"
        print(f"  {k:<16}{w['weight']:>8.2f}{ta:>11}{w['train_n']:>9}")

    def report(title, elig):
        ur = float(np.mean(up[elig])) if elig.any() else float("nan")
        print(f"\nTEST — {title}  (up-rate {ur*100:.0f}%, n={int(elig.sum())})")
        print(f"  {'model':<28}{'n':>5}{'acc':>8}{'base':>8}{'lift':>7}")
        rows = []
        for k in signals:
            s = acc_vs_baseline(signals[k], elig, up)
            if s: rows.append((k, s))
        for k, s in sorted(rows, key=lambda x: -x[1]["lift"]):
            print(f"  {k:<28}{s['n']:>5}{s['acc']*100:>7.1f}%{s['base']*100:>7.1f}%{s['lift']:>7.2f}")
        for label, call in (("confluence (equal-weight)", conf), ("ENSEMBLE (learned weights)", ens_call)):
            s = acc_vs_baseline(call, elig, up)
            if s:
                flag = "  <==" if "ENSEMBLE" in label else ""
                print(f"  {label:<28}{s['n']:>5}{s['acc']*100:>7.1f}%{s['base']*100:>7.1f}%{s['lift']:>7.2f}{flag}")

    report("all significant moves", test_elig)
    # post-squeeze slice of the test window
    bw = compute_indicators(candles)["bb_bandwidth"]
    squeeze = trailing_squeeze_mask(bw, window, pct)
    report("post-squeeze significant moves", test_elig & squeeze)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTC_USDT,ETH_USDT")
    ap.add_argument("--timeframe", default="1D")
    ap.add_argument("--horizon", type=int, default=5)
    ap.add_argument("--train-frac", type=float, default=0.6)
    ap.add_argument("--window", type=int, default=126)
    ap.add_argument("--pct", type=float, default=0.20)
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()]
    print(f"=== Calibrated ensemble walk-forward  tf={args.timeframe} horizon={args.horizon} "
          f"train_frac={args.train_frac} ===")
    with Store(args.db, read_only=True) as store:
        for s in syms:
            run_symbol(store, s, args.timeframe, args.horizon, args.train_frac, args.window, args.pct)
    print("\ndone.")


if __name__ == "__main__":
    main()
