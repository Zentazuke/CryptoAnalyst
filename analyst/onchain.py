"""On-chain network-activity read (free Coin Metrics community data).

Surfaces active-address and transaction trends, and the key insight: whether
on-chain activity is *diverging* from price (e.g. addresses rising while price
falls = accumulation/usage building under a falling tape — a bullish divergence).
Valuation metrics (MVRV/NVT) need a paid tier and are deliberately omitted.
"""
from __future__ import annotations

import numpy as np

from analyst.ingestion.coinmetrics import CoinMetricsSource


def _series(rows: list[dict], metric: str) -> tuple[list[str], np.ndarray]:
    times, vals = [], []
    for r in rows:
        v = r.get(metric)
        if v is not None:
            try:
                vals.append(float(v))
                times.append(r["time"])
            except (ValueError, TypeError):
                pass
    return times, np.array(vals, dtype=float)


def _trend(arr: np.ndarray, win: int = 30) -> float | None:
    """Sign-magnitude of recent vs prior window mean (relative change)."""
    if len(arr) < 2 * win:
        return None
    recent, prior = arr[-win:].mean(), arr[-2 * win:-win].mean()
    if prior <= 0:
        return None
    return float(recent / prior - 1.0)


def onchain_snapshot(symbol: str, days: int = 240, source: object | None = None) -> dict | None:
    """Network-activity snapshot for a symbol, or None if unavailable."""
    asset = symbol.split("_")[0].lower()
    src = source or CoinMetricsSource()
    rows = src.fetch_metrics(asset, ["AdrActCnt", "TxCnt", "PriceUSD"], days)
    if len(rows) < 40:
        return None

    _, addr = _series(rows, "AdrActCnt")
    _, txc = _series(rows, "TxCnt")
    _, price = _series(rows, "PriceUSD")
    if len(addr) < 40:
        return None

    addr_trend = _trend(addr)
    price_trend = _trend(price) if len(price) >= 60 else None
    addr_pct = float((addr[-90:] <= addr[-1]).mean()) if len(addr) >= 30 else None

    divergence = "none"
    if addr_trend is not None and price_trend is not None:
        if addr_trend > 0.02 and price_trend < -0.02:
            divergence = "bullish"   # usage up, price down
        elif addr_trend < -0.02 and price_trend > 0.02:
            divergence = "bearish"   # usage down, price up

    return {
        "asset": asset,
        "active_addresses": float(addr[-1]),
        "addr_trend_30d": round(addr_trend, 4) if addr_trend is not None else None,
        "addr_percentile_90d": round(addr_pct, 3) if addr_pct is not None else None,
        "tx_count": float(txc[-1]) if len(txc) else None,
        "tx_trend_30d": round(_trend(txc), 4) if _trend(txc) is not None else None,
        "price_trend_30d": round(price_trend, 4) if price_trend is not None else None,
        "divergence": divergence,
        "days": len(addr),
    }
