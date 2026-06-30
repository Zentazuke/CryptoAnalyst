"""Per-signal and per-combination directional calibration.

Answers, rigorously: which candle-derived signals (and which combinations)
actually predict the direction of the next move — and which only look like they
do? Every signal is scored on real (vol-scaled significant) moves with a Wilson
CI, a significance verdict, AND sub-period stability (does it hold in BOTH halves
of the sample, or just reshuffle like luck?).

The output is a ranked table you can trust: rely on signals that are
significant AND stable, discount the rest. Causal throughout (signals at bar i
use only data to i; outcomes are i+1..i+horizon).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from analyst.ensemble import directional_signals, forward_outcome
from analyst.stats import evidence


def _combinations(sig: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Build combination signals from the base set."""
    names = list(sig)
    n = len(sig[names[0]])
    stack = np.vstack([sig[k] for k in names])
    net = stack.sum(axis=0)

    combos: dict[str, np.ndarray] = {}
    maj = np.zeros(n)
    maj[net >= 2] = 1.0
    maj[net <= -2] = -1.0
    combos["COMBO majority(>=2)"] = maj

    aa = np.zeros(n)
    aa[np.all(stack > 0, axis=0)] = 1.0
    aa[np.all(stack < 0, axis=0)] = -1.0
    combos["COMBO all-agree"] = aa

    for a, b in [("ema_trend", "regime"), ("adx_di", "rsi_momentum"), ("ema_trend", "macd"),
                 ("regime", "adx_di")]:
        if a in sig and b in sig:
            c = np.zeros(n)
            agree = (sig[a] != 0) & (sig[a] == sig[b])
            c[agree] = sig[a][agree]
            combos[f"COMBO {a}+{b}"] = c
    return combos


def _score(call: np.ndarray, eligible: np.ndarray, up: np.ndarray):
    m = eligible & (call != 0)
    n = int(m.sum())
    if n == 0:
        return None
    hits = int(np.sum((call[m] > 0) == up[m]))
    up_rate = float(np.mean(up[m]))
    base = max(up_rate, 1 - up_rate)  # majority-class baseline accuracy
    return hits, n, base


def evaluate_signals(candles: list[Any], timeframe: str, horizon: int | None = None) -> dict:
    """Rank every signal + combination by measured directional edge, with CI,
    significance, and sub-period stability."""
    from analyst.commentary import DEFAULT_HORIZON
    horizon = horizon or DEFAULT_HORIZON.get(timeframe, 12)

    sig = directional_signals(candles)
    sig.update(_combinations(sig))
    up, significant, valid = forward_outcome(candles, horizon)
    elig = valid & significant
    n = len(up)
    idx = np.arange(n)
    mid = n // 2

    rows = []
    for name, call in sig.items():
        full = _score(call, elig, up)
        if not full:
            continue
        hits, nn, base = full
        ev = evidence(hits, nn, base)
        h1 = _score(call, elig & (idx < mid), up)
        h2 = _score(call, elig & (idx >= mid), up)

        def acc(s):
            return round(s[0] / s[1], 3) if s else None

        def beats(s):
            return bool(s and s[0] / s[1] > s[2])

        stable = beats(h1) and beats(h2)  # positive in BOTH halves
        rows.append({
            "signal": name, "n": ev["n"], "accuracy": ev["hit_rate"], "base": ev["base_rate"],
            "lift": ev["lift"], "ci_low": ev["ci_low"], "ci_high": ev["ci_high"],
            "verdict": ev["verdict"], "significant": ev["significant"],
            "h1_acc": acc(h1), "h2_acc": acc(h2), "stable": stable,
            "reliable": bool(ev["significant"] and stable),
        })
    rows.sort(key=lambda r: -(r["lift"] or 0))
    return {"timeframe": timeframe, "horizon": horizon, "signals": rows}
