"""Honest uncertainty for measured edges.

Every hit-rate the engine reports is an estimate from a finite sample. This
module attaches the error bars and a verdict so a thin or noisy sample cannot be
presented as a real edge:

  * ``wilson_interval`` — a Wilson score 95% CI for a proportion (well-behaved at
    small n and near 0/1, unlike the naive normal interval).
  * ``evidence`` — wraps a (hits, n, base_rate) measurement into hit-rate + CI,
    lift + CI, a two-sided p-value, and a verdict:
        "edge"         CI lies entirely above the base rate (significant)
        "negative"     CI lies entirely below the base rate (significantly worse)
        "no-edge"      CI straddles the base rate (no measurable difference)
        "insufficient" too few samples to judge (n < min_n)
        "no-data"      n == 0

The CI-vs-base-rate rule is the significance test: an edge is only called real
when the 95% interval excludes the base rate.
"""
from __future__ import annotations

import math

DEFAULT_Z = 1.96  # ~95%
MIN_SAMPLES = 30


def wilson_interval(hits: int, n: int, z: float = DEFAULT_Z) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. Returns (low, high)."""
    if n <= 0:
        return (0.0, 1.0)
    p = hits / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _two_sided_p(hits: int, n: int, p0: float) -> float | None:
    """Two-sided p-value (normal approx) for hit-rate vs a reference p0."""
    if n <= 0 or not (0.0 < p0 < 1.0):
        return None
    se = math.sqrt(p0 * (1 - p0) / n)
    if se == 0:
        return None
    z = (hits / n - p0) / se
    return math.erfc(abs(z) / math.sqrt(2.0))  # 2 * upper-tail


def evidence(hits: int, n: int, base_rate: float | None,
             z: float = DEFAULT_Z, min_n: int = MIN_SAMPLES) -> dict:
    """Measurement -> {hit_rate, ci, base_rate, lift, lift_ci, n, p_value, verdict}.

    Verdict is driven by whether the CI excludes the base rate (significance) and
    whether the sample is large enough to judge at all.
    """
    if n <= 0:
        return {"n": 0, "hit_rate": None, "ci_low": None, "ci_high": None,
                "base_rate": base_rate, "lift": None, "lift_ci_low": None,
                "lift_ci_high": None, "p_value": None, "significant": False,
                "verdict": "no-data"}

    p = hits / n
    lo, hi = wilson_interval(hits, n, z)
    lift = lift_lo = lift_hi = None
    if base_rate and base_rate > 0:
        lift = round(p / base_rate, 3)
        lift_lo = round(lo / base_rate, 3)
        lift_hi = round(hi / base_rate, 3)
    pval = _two_sided_p(hits, n, base_rate) if base_rate is not None else None

    if n < min_n:
        verdict, significant = "insufficient", False
    elif base_rate is None:
        verdict, significant = "no-edge", False
    elif lo > base_rate:
        verdict, significant = "edge", True
    elif hi < base_rate:
        verdict, significant = "negative", True
    else:
        verdict, significant = "no-edge", False

    return {
        "n": n,
        "hit_rate": round(p, 4),
        "ci_low": round(lo, 4),
        "ci_high": round(hi, 4),
        "base_rate": round(base_rate, 4) if base_rate is not None else None,
        "lift": lift,
        "lift_ci_low": lift_lo,
        "lift_ci_high": lift_hi,
        "p_value": round(pval, 4) if pval is not None else None,
        "significant": significant,
        "verdict": verdict,
    }
