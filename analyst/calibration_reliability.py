"""Reliability of the analyst's stated probabilities.

The signal study says *which* signals predict direction. This says whether the
numbers the analyst attaches to its calls are honest: when it claims confidence
p, does the event happen ~p of the time? Produces a reliability diagram + Brier
score, and an out-of-sample isotonic recalibration so the probabilities can be
*corrected* to mean what they say.

  * reliability_curve  — binned predicted vs observed frequency (the diagram).
  * brier_score        — mean squared (prob - outcome); lower is better.
  * calibration_report — curve + Brier + skill vs the base-rate forecast + bias.
  * recalibration_skill — fit isotonic on the past, score it on the future:
                          does recalibration genuinely improve Brier OOS?
"""
from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression


def reliability_curve(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> list[dict]:
    probs, outcomes = np.asarray(probs, float), np.asarray(outcomes, float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (probs >= lo) & (probs <= hi if i == n_bins - 1 else probs < hi)
        if m.sum() > 0:
            out.append({"lo": round(float(lo), 2), "hi": round(float(hi), 2),
                        "mean_pred": round(float(probs[m].mean()), 3),
                        "observed": round(float(outcomes[m].mean()), 3), "n": int(m.sum())})
    return out


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    probs, outcomes = np.asarray(probs, float), np.asarray(outcomes, float)
    return float(np.mean((probs - outcomes) ** 2))


def calibration_report(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> dict:
    probs, outcomes = np.asarray(probs, float), np.asarray(outcomes, float)
    if len(probs) < 30:
        return {"n": len(probs), "insufficient": True}
    base = float(outcomes.mean())
    brier = brier_score(probs, outcomes)
    brier_base = brier_score(np.full_like(outcomes, base), outcomes)  # always-predict-base
    return {
        "n": len(probs),
        "mean_pred": round(float(probs.mean()), 3),
        "observed_rate": round(base, 3),
        "calibration_bias": round(float(probs.mean() - base), 3),  # +overconfident, -underconfident
        "brier": round(brier, 4),
        "brier_baseline": round(brier_base, 4),
        "skill_score": round(1.0 - brier / brier_base, 4) if brier_base > 0 else None,
        "curve": reliability_curve(probs, outcomes, n_bins),
    }


def recalibration_skill(probs: np.ndarray, outcomes: np.ndarray, train_frac: float = 0.6) -> dict | None:
    """Fit isotonic recalibration on the past, score Brier on the future — does
    correcting the probabilities help out-of-sample?"""
    probs, outcomes = np.asarray(probs, float), np.asarray(outcomes, float)
    n = len(probs)
    if n < 80:
        return None
    sp = int(n * train_frac)
    iso = IsotonicRegression(out_of_bounds="clip").fit(probs[:sp], outcomes[:sp])
    raw_test = brier_score(probs[sp:], outcomes[sp:])
    cal_test = brier_score(iso.predict(probs[sp:]), outcomes[sp:])
    return {
        "n_test": n - sp,
        "brier_raw": round(raw_test, 4),
        "brier_recalibrated": round(cal_test, 4),
        "improved": cal_test < raw_test,
    }


def regime_confidence_pairs(candles, horizon: int):
    """(stated confidence, did-it-resolve-as-expected) pairs for directional regimes."""
    from analyst.ensemble import forward_outcome
    from analyst.regime import classify_series
    from analyst.regime import classifier as C
    res = classify_series(candles)
    up, _sig, valid = forward_outcome(candles, horizon)
    probs, outs = [], []
    for i, r in enumerate(res):
        if not valid[i]:
            continue
        if r.label == C.TREND_UP:
            expected_up = True
        elif r.label == C.TREND_DOWN:
            expected_up = False
        else:
            continue
        probs.append(float(r.confidence))
        outs.append(1.0 if bool(up[i]) == expected_up else 0.0)
    return np.array(probs, float), np.array(outs, float)
