"""Pure microstructure calculations.

Kept dependency-free and side-effect-free so they are trivially testable with
golden vectors, mirroring the trust discipline of the TA engine.
"""
from __future__ import annotations

Level = list[float]  # [price, size]


def mid_price(best_bid: float, best_ask: float) -> float:
    return (best_bid + best_ask) / 2.0


def spread_bps(best_bid: float, best_ask: float) -> float:
    """Top-of-book spread in basis points: (ask - bid) / mid * 10_000."""
    mid = mid_price(best_bid, best_ask)
    if mid <= 0:
        return float("nan")
    return (best_ask - best_bid) / mid * 10_000.0


def depth_within_band(
    levels: list[Level], mid: float, band_bps: float, side: str
) -> tuple[float, float]:
    """Sum resting liquidity within ``band_bps`` of mid on one side.

    Returns ``(base_qty, quote_notional)``. ``side`` is "bid" or "ask".
    Bids count from ``mid`` down to ``mid*(1 - band)``; asks from ``mid`` up to
    ``mid*(1 + band)``.
    """
    if side not in ("bid", "ask"):
        raise ValueError("side must be 'bid' or 'ask'")
    if mid <= 0:
        return 0.0, 0.0

    frac = band_bps / 10_000.0
    if side == "bid":
        lo = mid * (1.0 - frac)
        selected = [(p, s) for p, s in levels if lo <= p <= mid]
    else:
        hi = mid * (1.0 + frac)
        selected = [(p, s) for p, s in levels if mid <= p <= hi]

    base = sum(s for _, s in selected)
    quote = sum(p * s for p, s in selected)
    return base, quote


def basis_bps(mark: float | None, index: float | None) -> float | None:
    """Perpetual basis in basis points: (mark - index) / index * 10_000."""
    if mark is None or index is None or index == 0:
        return None
    return (mark - index) / index * 10_000.0
