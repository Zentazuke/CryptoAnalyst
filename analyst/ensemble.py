"""Calibrated directional ensemble.

Turns the backtest scorecard into a usable signal: weight each candle-derived
metric by its *measured* directional edge on a training window, then combine the
weighted votes into one score. Honest by construction:

  * a signal with no edge earns a weight near zero,
  * an anti-predictive signal earns a *negative* weight (the ensemble fades it),
  * weights are learned only from training data and applied unchanged out of
    sample, so the walk-forward evaluation never peeks at the future.

All inputs are the engine's existing causal indicators / regime series.
"""
from __future__ import annotations

import math

import numpy as np

from analyst.features import indicators as I
from analyst.features.engine import compute_indicators
from analyst.regime import classifier as C
from analyst.stats import evidence

MOVE_K = 1.0  # vol-scaled significance multiplier (matches the regime calibrator)

# the candle-derived signals that have >=5y of history to calibrate on
SIGNAL_NAMES = ["ema_trend", "bb_position", "macd", "rsi_momentum", "adx_di", "regime"]


def directional_signals(candles) -> dict[str, np.ndarray]:
    """Per-bar directional calls in {+1, -1, 0}. Strictly causal."""
    close = np.array([c["close"] for c in candles], float)
    high = np.array([c["high"] for c in candles], float)
    low = np.array([c["low"] for c in candles], float)
    ind = compute_indicators(candles)
    labels = np.array([r.label for r in C.classify_series(candles)], dtype=object)
    n = len(close)

    def sgt(a, b):
        out = np.zeros(n)
        m = np.isfinite(a) & np.isfinite(b)
        out[m] = np.where(a[m] > b[m], 1.0, -1.0)
        return out

    sig: dict[str, np.ndarray] = {}
    sig["ema_trend"] = sgt(close, ind["ema_20"])
    sig["bb_position"] = sgt(close, ind["bb_mid"])
    sig["macd"] = sgt(ind["macd"], ind["macd_signal"])

    rsi = ind["rsi_14"]
    r = np.zeros(n)
    r[np.isfinite(rsi) & (rsi > 55)] = 1.0
    r[np.isfinite(rsi) & (rsi < 45)] = -1.0
    sig["rsi_momentum"] = r

    adx, pdi, mdi = ind["adx_14"], ind["plus_di"], ind["minus_di"]
    d = np.zeros(n)
    t = np.isfinite(adx) & (adx >= 20) & np.isfinite(pdi) & np.isfinite(mdi)
    d[t] = np.where(pdi[t] > mdi[t], 1.0, -1.0)
    sig["adx_di"] = d

    g = np.zeros(n)
    g[labels == C.TREND_UP] = 1.0
    g[labels == C.TREND_DOWN] = -1.0
    sig["regime"] = g
    return sig


def forward_outcome(candles, horizon: int):
    """Per-bar (realized_up, significant, valid) over a vol-scaled threshold."""
    close = np.array([c["close"] for c in candles], float)
    high = np.array([c["high"] for c in candles], float)
    low = np.array([c["low"] for c in candles], float)
    atr = I.atr(high, low, close, 14)
    n = len(close)
    sh = math.sqrt(horizon)
    up = np.zeros(n, dtype=bool)
    sig = np.zeros(n, dtype=bool)
    valid = np.zeros(n, dtype=bool)
    for i in range(n - horizon):
        if not (np.isfinite(close[i]) and np.isfinite(atr[i]) and close[i] > 0):
            continue
        ret = close[i + horizon] / close[i] - 1.0
        thr = MOVE_K * (atr[i] / close[i]) * sh
        valid[i] = True
        up[i] = ret > 0
        sig[i] = abs(ret) > thr
    return up, sig, valid


def learn_weights(signals: dict[str, np.ndarray], up: np.ndarray, eligible: np.ndarray,
                  min_samples: int = 20) -> dict[str, dict]:
    """weight = 2*accuracy - 1 over training bars where the signal makes a call.

    Edge in [-1, 1]: positive = predictive, negative = fade it, ~0 = useless.
    Signals with too few training samples get zero weight.
    """
    out: dict[str, dict] = {}
    for name, call in signals.items():
        m = eligible & (call != 0)
        n = int(m.sum())
        if n < min_samples:
            out[name] = {"weight": 0.0, "train_n": n, "train_acc": None}
            continue
        acc = float(np.mean((call[m] > 0) == up[m]))
        out[name] = {"weight": 2.0 * acc - 1.0, "train_n": n, "train_acc": acc}
    return out


def ensemble_calls(signals: dict[str, np.ndarray], weights: dict[str, dict]):
    """Weighted vote -> (call in {+1,-1,0}, raw score). call=0 when score==0."""
    n = len(next(iter(signals.values())))
    score = np.zeros(n)
    for name, call in signals.items():
        score += weights.get(name, {}).get("weight", 0.0) * call
    out = np.zeros(n)
    out[score > 0] = 1.0
    out[score < 0] = -1.0
    return out, score


def directional_accuracy(call: np.ndarray, eligible: np.ndarray, up: np.ndarray) -> dict | None:
    """Accuracy vs the majority-class baseline, with a confidence interval and a
    significance verdict (so a thin/noisy sample can't pass as an edge)."""
    m = eligible & (call != 0)
    n = int(m.sum())
    if n == 0:
        return None
    hits = int(np.sum((call[m] > 0) == up[m]))
    up_rate = float(np.mean(up[m]))
    base = max(up_rate, 1 - up_rate)  # majority-class baseline accuracy
    return evidence(hits, n, base)


def ensemble_read(candles, timeframe: str, horizon: int | None = None,
                  train_frac: float = 0.6) -> dict | None:
    """The current weighted directional lean, with its out-of-sample track record.

    Weights for the live lean are learned from all *resolved* history (causal —
    each weight uses only past forward-outcomes). The track record is measured
    walk-forward: weights learned on the early `train_frac`, scored on the held-
    out remainder, so the reported lift is honest out-of-sample.
    """
    from analyst.commentary import DEFAULT_HORIZON

    n = len(candles)
    if n < 250:
        return None
    horizon = horizon or DEFAULT_HORIZON.get(timeframe, 12)
    signals = directional_signals(candles)
    up, significant, valid = forward_outcome(candles, horizon)
    idx = np.arange(n)
    elig_all = valid & significant

    weights = learn_weights(signals, up, elig_all)
    _, score_arr = ensemble_calls(signals, weights)

    # honest out-of-sample track record for this ensemble
    split = int(n * train_frac)
    w_train = learn_weights(signals, up, elig_all & (idx < split - horizon))
    test_call, _ = ensemble_calls(signals, w_train)
    track = directional_accuracy(test_call, elig_all & (idx >= split), up)

    last = n - 1
    contributions: dict[str, dict] = {}
    active_abs = 0.0
    for name, arr in signals.items():
        c = float(arr[last])
        w = weights[name]["weight"]
        if c != 0:
            active_abs += abs(w)
        contributions[name] = {
            "weight": round(w, 3), "call": c, "contribution": round(w * c, 3),
            "train_acc": weights[name]["train_acc"], "train_n": weights[name]["train_n"],
        }
    score = float(score_arr[last])
    norm = score / active_abs if active_abs > 0 else 0.0
    lean = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"
    return {
        "horizon": horizon,
        "lean": lean,
        "score": round(score, 3),
        "normalized": round(norm, 3),  # -1..1: agreement of the active signals
        "signals": contributions,
        "calibration": track,  # {n, acc, base, lift} out-of-sample, or None
    }
