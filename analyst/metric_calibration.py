"""P1.2 — calibrate ANY persisted metric series the SIGNAL_CARD way.

The upgrade plan's rule made executable: a sentiment or on-chain series recorded
by MetricHistory (P1.1) earns a place in the UI/composite ONLY by passing the
same bar as the candle signals — accuracy on vol-scaled significant moves vs the
majority baseline, Wilson CI, significance, and BOTH-HALVES stability.

Signal convention (fixed a priori — per-metric rule shopping is the mining trap):
the call at a bar is the latest observation vs the median of its prior `window`
observations: above -> +1, below -> -1. Because a metric's *sense* is unknown
(a fear index is bearish-when-high), BOTH orientations are scored and reported.
Two orientations = double the luck surface, so the verdict discounts that:
`reliable` additionally requires the SAME orientation to win in both halves —
and the caller must treat the losing orientation as disproven, not "the other
option". Staleness guard: no call when the freshest observation is older than
`stale_factor` x the series' own median spacing.

Pure functions over (series, candles) — no store, no network.
"""
from __future__ import annotations

import bisect
import math
from typing import Any

import numpy as np

from analyst.ensemble import forward_outcome
from analyst.signal_eval import _score
from analyst.stats import evidence

DEFAULT_WINDOW = 60          # trailing observations for the median baseline
STALE_FACTOR = 3.0           # freshest obs older than 3x median spacing -> no call


def metric_calls(series: list[dict], candle_ts: list[int],
                 window: int = DEFAULT_WINDOW,
                 stale_factor: float = STALE_FACTOR) -> np.ndarray:
    """Per-candle-bar call in {+1,-1,0} from a [{ts, value}] series (ms, sorted).
    Causal: a bar only sees observations with ts <= the bar's ts."""
    n = len(candle_ts)
    calls = np.zeros(n)
    if len(series) < window + 1:
        return calls
    obs_ts = [int(r["ts"]) for r in series]
    vals = np.array([float(r["value"]) for r in series])

    sigs = np.zeros(len(vals))
    for k in range(window, len(vals)):
        med = float(np.median(vals[k - window:k]))
        sigs[k] = 1.0 if vals[k] > med else (-1.0 if vals[k] < med else 0.0)

    gaps = np.diff(obs_ts)
    max_age = stale_factor * float(np.median(gaps)) if len(gaps) else float("inf")
    for i, t in enumerate(candle_ts):
        k = bisect.bisect_right(obs_ts, t) - 1
        if k >= window and (t - obs_ts[k]) <= max_age:
            calls[i] = sigs[k]
    return calls


def evaluate_metric(name: str, series: list[dict], candles: list[Any],
                    timeframe: str, horizon: int | None = None,
                    window: int = DEFAULT_WINDOW) -> dict:
    """Score one stored series against forward outcomes, both orientations.

    Returns {metric, timeframe, horizon, n_obs, rows: [...]} — rows sorted by
    lift, one per orientation ('high_bullish' / 'high_bearish'), each with the
    full evidence set. Caller rule: at most ONE orientation may ever be claimed."""
    from analyst.commentary import DEFAULT_HORIZON  # deferred, as in signal_eval
    horizon = horizon or DEFAULT_HORIZON.get(timeframe, 12)

    candle_ts = [int(c["ts"]) for c in candles]
    base_calls = metric_calls(series, candle_ts, window=window)
    up, significant, valid = forward_outcome(candles, horizon)
    elig = valid & significant
    idx = np.arange(len(up))
    mid = len(up) // 2

    rows = []
    for orient, label in ((1.0, "high_bullish"), (-1.0, "high_bearish")):
        call = base_calls * orient
        full = _score(call, elig, up)
        if not full:
            continue
        hits, n, base = full
        ev = evidence(hits, n, base)
        h1 = _score(call, elig & (idx < mid), up)
        h2 = _score(call, elig & (idx >= mid), up)

        def acc(s):
            return round(s[0] / s[1], 3) if s else None

        def beats(s):
            return bool(s and s[0] / s[1] > s[2])

        stable = beats(h1) and beats(h2)
        rows.append({
            "metric": name, "orientation": label,
            "n": ev["n"], "accuracy": ev["hit_rate"], "base": ev["base_rate"],
            "lift": ev["lift"], "ci_low": ev["ci_low"], "ci_high": ev["ci_high"],
            "verdict": ev["verdict"], "significant": ev["significant"],
            "h1_acc": acc(h1), "h2_acc": acc(h2), "stable": stable,
            "reliable": bool(ev["significant"] and stable),
        })
    rows.sort(key=lambda r: -(r["lift"] or 0))
    return {"metric": name, "timeframe": timeframe, "horizon": horizon,
            "n_obs": len(series), "window": window, "rows": rows,
            "note": "Both orientations are scored; claiming whichever looks better "
                    "doubles the luck surface — only a `reliable` row (significant "
                    "AND stable in both halves) counts, and its mirror is disproven."}


def best_row(report: dict) -> dict | None:
    """The single defensible row of a report: the top reliable one, else None."""
    for r in report.get("rows", []):
        if r.get("reliable"):
            return r
    return None
