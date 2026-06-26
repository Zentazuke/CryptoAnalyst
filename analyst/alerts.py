"""Proactive, confluence-ranked alerts across the scanned market.

We measured that agreement beats single signals, so alerts fire only when
multiple signals corroborate — and are ranked by how many. Built from the
market-scan rows (regime, momentum, RSI, funding, EMA position), so it adds no
extra fetches.
"""
from __future__ import annotations

from analyst.regime import classifier as C


def detect_alerts(rows: list[dict], *, mom_thr: float = 0.03, funding_extreme: float = 0.0003) -> list[dict]:
    """Return confluence setups, ranked by corroborating-signal count (severity)."""
    alerts: list[dict] = []

    price_by_sym: dict[str, float] = {}

    def add(sym, kind, direction, signals, note, boost=0):
        alerts.append({
            "symbol": sym, "kind": kind, "direction": direction,
            "severity": len(signals) + boost, "signals": signals, "note": note,
            "price": price_by_sym.get(sym),
        })

    for r in rows:
        sym, regime = r["symbol"], r["regime"]
        price_by_sym[sym] = r.get("price")
        rsi, funding = r.get("rsi"), r.get("funding")
        mom = r.get("momentum") or 0.0
        above, _ = r.get("above_ema"), r.get("adx")

        # aligned trend-up
        bull = []
        if regime == C.TREND_UP:
            bull.append("uptrend")
        if mom > mom_thr:
            bull.append(f"+{mom * 100:.0f}% momentum")
        if above:
            bull.append("above EMA20")
        if rsi is not None and 50 <= rsi < 70:
            bull.append(f"RSI {rsi:.0f}")
        if len(bull) >= 3:
            add(sym, "trend-up", "bull", bull, "aligned bullish: " + ", ".join(bull))

        # aligned trend-down
        bear = []
        if regime == C.TREND_DOWN:
            bear.append("downtrend")
        if mom < -mom_thr:
            bear.append(f"{mom * 100:.0f}% momentum")
        if above is False:
            bear.append("below EMA20")
        if rsi is not None and 30 < rsi <= 50:
            bear.append(f"RSI {rsi:.0f}")
        if len(bear) >= 3:
            add(sym, "trend-down", "bear", bear, "aligned bearish: " + ", ".join(bear))

        # contrarian: crowded longs (flush risk)
        if funding is not None and funding > funding_extreme:
            sig = [f"funding {funding * 100:+.3f}%"]
            if rsi is not None and rsi > 65:
                sig.append(f"RSI {rsi:.0f} overbought")
            if regime == C.TREND_UP:
                sig.append("extended uptrend")
            if len(sig) >= 2:
                add(sym, "crowded-long", "bear", sig,
                    "crowded longs + " + ", ".join(sig[1:]) + " — flush / contrarian-bearish risk", boost=1)

        # contrarian: crowded shorts (squeeze setup)
        if funding is not None and funding < -funding_extreme:
            sig = [f"funding {funding * 100:+.3f}%"]
            if rsi is not None and rsi < 35:
                sig.append(f"RSI {rsi:.0f} oversold")
            if regime in (C.RANGE, C.LOW_VOL_DRIFT):
                sig.append("ranging")
            if len(sig) >= 2:
                add(sym, "crowded-short", "bull", sig,
                    "crowded shorts + " + ", ".join(sig[1:]) + " — squeeze / contrarian-bullish setup", boost=1)

        # outright RSI extreme
        if rsi is not None and (rsi < 20 or rsi > 80):
            add(sym, "rsi-extreme", "bull" if rsi < 20 else "bear", [f"RSI {rsi:.0f}"],
                f"RSI {rsi:.0f} — {'deeply oversold' if rsi < 20 else 'deeply overbought'}")

    alerts.sort(key=lambda a: a["severity"], reverse=True)
    return alerts[:15]
