"""Implied vs realized volatility.

Compares Deribit's DVOL (annualized implied vol) to the asset's annualized
realized vol. A premium (implied > realized) means options are pricing more
risk than has occurred — demand for protection / fear; a discount means options
look cheap vs what price is actually doing. BTC/ETH only (DVOL coverage).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from analyst.ingestion.deribit import DeribitSource

PERIODS_PER_YEAR = {"1m": 525600, "5m": 105120, "15m": 35040, "30m": 17520,
                    "1h": 8760, "4h": 2190, "12h": 730, "1D": 365, "7D": 52}


def implied_vol_context(
    symbol: str, candles: list[Any], timeframe: str, rv_window: int = 100, source: object | None = None,
) -> dict | None:
    cur = symbol.split("_")[0].upper()
    src = source or DeribitSource()
    dvol = src.fetch_dvol(cur)
    if dvol is None:
        return None

    close = np.array([c["close"] if isinstance(c, dict) else c.close for c in candles], float)
    if len(close) < 30:
        return None
    logret = np.diff(np.log(close))
    rv_bar = float(np.std(logret[-rv_window:], ddof=0))
    rv_annual = rv_bar * math.sqrt(PERIODS_PER_YEAR.get(timeframe, 8760)) * 100.0
    premium = dvol - rv_annual
    signal = "premium" if premium > 5 else "discount" if premium < -5 else "fair"
    return {
        "dvol": round(dvol, 1),
        "realized_vol_annual": round(rv_annual, 1),
        "premium_pts": round(premium, 1),
        "signal": signal,
    }
