"""Live variance-risk-premium read — the cockpit for the one strategy that works.

Not a prediction: a *framing*. Shows where the current implied-vs-realized spread
(the premium you'd be paid to sell vol) sits versus its own history, and whether
that's rich, fair, or cheap right now. BTC/ETH only (DVOL coverage).

  premium      = implied (DVOL, 30d) - trailing 30d realized vol   [vol points]
  percentile   = where today's premium ranks in its own history
  verdict      = rich (well-paid to sell) / fair / cheap (stand aside)

The defined-risk framing (cap the tail by structure, not timing) is carried in
the recommendation text — consistent with the VRP model card.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from analyst.ingestion.deribit import DeribitSource

DAY_MS = 86_400_000
RV_WINDOW = 30


def _closes_days(candles: list[Any]) -> tuple[np.ndarray, np.ndarray]:
    cl = np.array([(c["close"] if isinstance(c, dict) else c.close) for c in candles], float)
    ts = np.array([(c["ts"] if isinstance(c, dict) else c.ts) for c in candles], np.int64)
    return cl, ts // DAY_MS


def vrp_read(currency: str, daily_candles: list[Any], source: object | None = None) -> dict | None:
    """Current VRP read for BTC/ETH, or None if DVOL/history is unavailable."""
    ds = source or DeribitSource()
    dvh = ds.fetch_dvol_history(currency, days=2000, resolution=86400)
    if not dvh or len(daily_candles) < RV_WINDOW + 30:
        return None
    dvol_by_day = {r["ts"] // DAY_MS: r["dvol"] for r in dvh}

    cl, days = _closes_days(daily_candles)
    rets = np.diff(np.log(cl))

    premiums, realized_last, implied_last = [], None, None
    for t in range(RV_WINDOW, len(cl)):
        d = int(days[t])
        iv = dvol_by_day.get(d)
        if iv is None:
            continue
        rv = float(np.std(rets[t - RV_WINDOW: t], ddof=0) * math.sqrt(365) * 100.0)
        premiums.append(iv - rv)
        realized_last, implied_last = rv, iv
    if len(premiums) < 60 or implied_last is None:
        return None

    premiums = np.array(premiums, float)
    cur = float(premiums[-1])
    pctl = float((premiums < cur).mean())
    verdict = "rich" if pctl >= 0.66 else "cheap" if pctl <= 0.33 else "fair"
    # Honest framing: the premium is real but a real structure backtest showed the
    # retail defined-risk harvest is net-negative (fat tails). This is a gauge,
    # not a trade signal — see VRP_MODEL_CARD.md.
    rec = {
        "rich": "Premium is high vs its history. NOTE: this is context, not a trade signal — the retail "
                "defined-risk harvest (iron condor) tested net-negative; only daily delta-hedged variance "
                "captures it. A gauge, not a green light to sell.",
        "fair": "Premium is middling — nothing to act on; the retail harvest doesn't clear costs anyway.",
        "cheap": "Vol is cheap vs realized — if anything a long-gamma context, but not a tradeable signal here.",
    }[verdict]

    return {
        "currency": currency.upper(),
        "implied_vol_dvol": round(implied_last, 1),
        "realized_vol_30d": round(realized_last, 1),
        "premium_volpts": round(cur, 1),
        "premium_percentile": round(pctl, 2),
        "premium_median": round(float(np.median(premiums)), 1),
        "verdict": verdict,
        "recommendation": rec,
        "samples": len(premiums),
        # honest harvest note (NOT a validated retail trade — see VRP_MODEL_CARD.md)
        "trade": {"harvestable_retail": False,
                  "note": "premium real, but retail defined-risk loses to fat tails; only daily "
                          "delta-hedged variance harvests it (institutional). Context, not a trade."},
    }
