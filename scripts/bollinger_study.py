"""Bollinger-squeeze directional-predictability study.

Question: when the Bollinger band is *squeezed* (compressed), can any of the
engine's metrics predict the DIRECTION of the expansion that follows? And does a
squeeze precede a bigger move at all (the magnitude claim)?

Method (strictly causal, no look-ahead):
  * features at bar i come from the engine's causal indicators / regime series.
  * a bar is "squeezed" if its Bollinger bandwidth is in the bottom `pct` of a
    trailing window (past data only).
  * the forward outcome over `horizon` bars is the realized return; a move only
    counts as a real "expansion" if it clears a volatility-scaled threshold
    (move_k * atr_pct * sqrt(horizon)) — the same yardstick the regime
    calibrator uses, so we are not scoring noise.
  * each predictor emits an up/down call at bar i; we measure directional
    accuracy vs the majority-class baseline (could you beat always guessing the
    dominant direction on the same bars?). lift = accuracy / baseline.

Run:
    python -m scripts.bollinger_study --symbols BTC_USDT,ETH_USDT --timeframe 1D --horizon 5
"""
from __future__ import annotations

import argparse
import math

import numpy as np

from analyst.config import DB_PATH
from analyst.features.engine import compute_indicators
from analyst.regime import classifier as C
from analyst.storage import Store

MOVE_K = 1.0  # significance threshold multiplier (matches the regime calibrator)


def _arr(candles, key):
    return np.array([c[key] for c in candles], float)


def trailing_squeeze_mask(bw: np.ndarray, window: int, pct: float) -> np.ndarray:
    """True where bandwidth sits in the bottom `pct` of the trailing `window`."""
    n = len(bw)
    mask = np.zeros(n, dtype=bool)
    for i in range(window, n):
        seg = bw[i - window + 1 : i + 1]
        if not np.isfinite(bw[i]):
            continue
        seg = seg[np.isfinite(seg)]
        if len(seg) < window // 2:
            continue
        rank = np.mean(seg <= bw[i])  # causal percentile rank of the current bar
        mask[i] = rank <= pct
    return mask


def predictors(ind: dict, regimes, close: np.ndarray):
    """Each predictor -> array of directional calls in {+1, -1, 0} per bar."""
    ema = ind["ema_20"]
    rsi = ind["rsi_14"]
    macd, macd_sig = ind["macd"], ind["macd_signal"]
    adx, pdi, mdi = ind["adx_14"], ind["plus_di"], ind["minus_di"]
    bb_mid = ind["bb_mid"]
    labels = np.array([r.label for r in regimes], dtype=object)
    n = len(close)

    def sign_gt(a, b):
        out = np.zeros(n)
        m = np.isfinite(a) & np.isfinite(b)
        out[m] = np.where(a[m] > b[m], 1.0, -1.0)
        return out

    preds: dict[str, np.ndarray] = {}
    preds["ema_trend (close vs EMA20)"] = sign_gt(close, ema)
    preds["bb_position (close vs mid)"] = sign_gt(close, bb_mid)
    preds["macd (line vs signal)"] = sign_gt(macd, macd_sig)

    # RSI momentum: >55 up, <45 down, else no call
    r = np.zeros(n)
    r[np.isfinite(rsi) & (rsi > 55)] = 1.0
    r[np.isfinite(rsi) & (rsi < 45)] = -1.0
    preds["rsi_momentum (>55 / <45)"] = r

    # ADX/DI: directional only when a trend is present (adx >= 20)
    d = np.zeros(n)
    trend = np.isfinite(adx) & (adx >= 20) & np.isfinite(pdi) & np.isfinite(mdi)
    d[trend] = np.where(pdi[trend] > mdi[trend], 1.0, -1.0)
    preds["adx_di (+DI/-DI, adx>=20)"] = d

    # Regime: directional labels only
    g = np.zeros(n)
    g[labels == C.TREND_UP] = 1.0
    g[labels == C.TREND_DOWN] = -1.0
    g[labels == C.BREAKOUT] = 0.0  # breakout has no inherent direction
    preds["regime (trend_up/down)"] = g

    # Breakout-follow: direction of the move into the squeeze (close vs 5 bars ago)
    bf = np.zeros(n)
    for i in range(5, n):
        if np.isfinite(close[i]) and np.isfinite(close[i - 5]):
            bf[i] = 1.0 if close[i] >= close[i - 5] else -1.0
    preds["breakout_follow (prior 5-bar)"] = bf

    # Confluence: net vote of EMA, MACD, regime, ADX/DI; call only if |net| >= 2
    votes = preds["ema_trend (close vs EMA20)"] + preds["macd (line vs signal)"] + g + d
    conf = np.zeros(n)
    conf[votes >= 2] = 1.0
    conf[votes <= -2] = -1.0
    preds["confluence (>=2 of 4 agree)"] = conf
    return preds


def score(call: np.ndarray, eligible: np.ndarray, realized_up: np.ndarray):
    """Directional accuracy vs majority-class baseline over called+eligible bars."""
    m = eligible & (call != 0)
    n = int(m.sum())
    if n == 0:
        return None
    correct = int(np.sum((call[m] > 0) == realized_up[m]))
    acc = correct / n
    up_rate = float(np.mean(realized_up[m]))
    baseline = max(up_rate, 1 - up_rate)  # always-guess-majority accuracy
    lift = acc / baseline if baseline > 0 else float("nan")
    return {"n": n, "acc": acc, "up_rate": up_rate, "baseline": baseline, "lift": lift}


def run_symbol(store: Store, symbol: str, timeframe: str, horizon: int, window: int, pct: float):
    candles = store.get_candles(symbol, timeframe)
    n = len(candles)
    if n < window + horizon + 50:
        print(f"  {symbol}: not enough history ({n} bars)"); return
    close = _arr(candles, "close")
    high, low = _arr(candles, "high"), _arr(candles, "low")
    ind = compute_indicators(candles)
    from analyst.features import indicators as I
    atr = I.atr(high, low, close, 14)
    regimes = C.classify_series(candles)
    bw = ind["bb_bandwidth"]

    squeeze = trailing_squeeze_mask(bw, window, pct)

    # forward outcome + significance (vol-scaled), strictly i+1..i+horizon
    sqrt_h = math.sqrt(horizon)
    realized_up = np.zeros(n, dtype=bool)
    significant = np.zeros(n, dtype=bool)
    valid = np.zeros(n, dtype=bool)
    fwd_abs = np.full(n, np.nan)
    for i in range(n - horizon):
        if not (np.isfinite(close[i]) and np.isfinite(atr[i]) and close[i] > 0):
            continue
        ret = close[i + horizon] / close[i] - 1.0
        thr = MOVE_K * (atr[i] / close[i]) * sqrt_h
        valid[i] = True
        realized_up[i] = ret > 0
        significant[i] = abs(ret) > thr
        fwd_abs[i] = abs(ret)

    base_window = valid & np.isfinite(bw)
    sq = squeeze & valid
    # magnitude claim: do squeezed bars precede bigger moves?
    mag_sq = np.nanmean(fwd_abs[sq]) if sq.any() else float("nan")
    mag_non = np.nanmean(fwd_abs[base_window & ~squeeze]) if (base_window & ~squeeze).any() else float("nan")
    exp_rate_sq = float(np.mean(significant[sq])) if sq.any() else float("nan")
    exp_rate_non = float(np.mean(significant[base_window & ~squeeze])) if (base_window & ~squeeze).any() else float("nan")

    print(f"\n================  {symbol}  {timeframe}  ================")
    print(f"bars={n}  squeeze bars={int(sq.sum())}  horizon={horizon}  window={window}  pct={pct}")
    print("\nMAGNITUDE (does a squeeze precede a bigger move?)")
    print(f"  mean |fwd move|   squeeze: {mag_sq*100:5.2f}%   non-squeeze: {mag_non*100:5.2f}%   "
          f"ratio {mag_sq/mag_non:.2f}x" if np.isfinite(mag_sq) and np.isfinite(mag_non) and mag_non else "  n/a")
    print(f"  significant-move rate   squeeze: {exp_rate_sq*100:4.0f}%   non-squeeze: {exp_rate_non*100:4.0f}%")

    preds = predictors(ind, regimes, close)

    def table(title, eligible):
        up = float(np.mean(realized_up[eligible])) if eligible.any() else float("nan")
        print(f"\nDIRECTION — {title}   (universe up-rate {up*100:.0f}%, n={int(eligible.sum())})")
        print(f"  {'predictor':<30} {'n':>5} {'acc':>7} {'baseline':>9} {'lift':>6}")
        rows = []
        for name, call in preds.items():
            s = score(call, eligible, realized_up)
            if s:
                rows.append((name, s))
        for name, s in sorted(rows, key=lambda x: -x[1]["lift"]):
            flag = "  <-- edge" if s["lift"] >= 1.05 and s["n"] >= 25 else ""
            print(f"  {name:<30} {s['n']:>5} {s['acc']*100:6.1f}% {s['baseline']*100:8.1f}% {s['lift']:>6.2f}{flag}")

    # only score on bars where a real expansion actually happened
    table("after a SQUEEZE (significant moves only)", sq & significant)
    table("ALL bars (significant moves only) — for comparison", base_window & significant)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTC_USDT,ETH_USDT")
    ap.add_argument("--timeframe", default="1D")
    ap.add_argument("--horizon", type=int, default=5)
    ap.add_argument("--window", type=int, default=126, help="trailing window for the squeeze percentile")
    ap.add_argument("--pct", type=float, default=0.20, help="bottom-percentile bandwidth = squeeze")
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()]
    print(f"=== Bollinger squeeze directional study  tf={args.timeframe} horizon={args.horizon} "
          f"window={args.window} pct={args.pct} ===")
    with Store(args.db, read_only=True) as store:
        for s in syms:
            run_symbol(store, s, args.timeframe, args.horizon, args.window, args.pct)
    print("\ndone.")


if __name__ == "__main__":
    main()
