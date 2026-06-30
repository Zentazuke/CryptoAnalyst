"""Funding-carry read — a real market observable, framed honestly.

A delta-neutral position (long spot / short perp) collects the perpetual funding
rate. When funding is positive, that's a structural carry yield. The postmortem
verdict: real but *compressing* and *tail-risky* (a deleveraging spikes funding
negative and the basis gaps) — so this is **context, not alpha**. The analyst
surfaces the current annualized carry, where it sits vs history, and whether it's
compressing.
"""
from __future__ import annotations

import numpy as np

FUNDING_PER_DAY = 3  # 8-hour funding periods


def carry_read(funding_rows: list[dict], recent: int = 90, long_w: int = 540) -> dict | None:
    """Annualized delta-neutral funding carry + percentile + compression flag.

    `recent`/`long_w` are counts of 8h funding periods (90 ~= 30d, 540 ~= 180d).
    """
    vals = []
    for r in funding_rows:
        v = r.get("v", r.get("funding_rate"))
        if v is not None:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
    vals = np.array(vals, float)
    if len(vals) < recent:
        return None

    def ann(window: np.ndarray) -> float:
        return float(np.mean(window) * FUNDING_PER_DAY * 365 * 100)

    cur = ann(vals[-recent:])
    hist = [ann(vals[i - recent:i]) for i in range(recent, len(vals))]
    pctl = float((np.array(hist) < cur).mean()) if hist else None
    long_avg = ann(vals[-long_w:]) if len(vals) >= long_w else ann(vals)
    return {
        "carry_annual_pct": round(cur, 1),
        "current_funding_8h_pct": round(float(vals[-1]) * 100, 4),
        "percentile": round(pctl, 2) if pctl is not None else None,
        "long_avg_annual_pct": round(long_avg, 1),
        "compressing": bool(cur < long_avg),
        "samples": len(vals),
        "note": "delta-neutral (long spot / short perp) carry. Real but compressing and tail-risky "
                "in a deleveraging — context, not alpha.",
    }
