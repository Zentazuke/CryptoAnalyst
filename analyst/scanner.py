"""Cross-asset market scanner.

The research's clearest finding was that edge lives in breadth and
cross-sectional structure, not single-asset timing. This scans the top liquid
coins and, per coin, computes the regime, momentum (relative strength), and
funding — then ranks them, summarises market breadth, and surfaces standout
setups. Everything is the analyst's own causal engine, applied widely.
"""
from __future__ import annotations

from typing import Any

from analyst.features import snapshot
from analyst.regime import classify_latest
from analyst.regime import classifier as C


def _base(sym: str, quote: str = "USDT") -> str:
    return sym[: -len(quote)] if sym.endswith(quote) else sym


def scan_symbols(
    source: Any, symbols: list[str], timeframe: str = "4h",
    count: int = 200, lookback: int = 30,
) -> dict:
    """Scan ``symbols``: per-coin regime + momentum + funding, ranked + summarised."""
    funding = source.fetch_all_funding() if hasattr(source, "fetch_all_funding") else {}

    rows: list[dict] = []
    for sym in symbols:
        try:
            candles, _ = source.fetch_ohlcv(sym, timeframe, count)
        except Exception:
            continue
        if len(candles) < 60:
            continue
        reg = classify_latest(candles)
        vals = snapshot(candles)["values"]
        closes = [c.close for c in candles]
        lb = min(lookback, len(closes) - 1)
        price = closes[-1]
        ema = vals.get("ema_20")
        rows.append({
            "symbol": _base(sym),
            "instrument": sym,
            "price": price,
            "regime": reg.label,
            "confidence": reg.confidence,
            "rsi": vals.get("rsi_14"),
            "adx": vals.get("adx_14"),
            "above_ema": ema is not None and price > ema,
            "momentum": price / closes[-1 - lb] - 1.0,
            "funding": funding.get(sym),
        })

    rows.sort(key=lambda r: r["momentum"] if r["momentum"] is not None else -9, reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1

    return {
        "timeframe": timeframe,
        "lookback": lookback,
        "count": len(rows),
        "rows": rows,
        "aggregates": _aggregate(rows),
        "setups": _setups(rows),
    }


def _aggregate(rows: list[dict]) -> dict:
    n = len(rows) or 1
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["regime"]] = counts.get(r["regime"], 0) + 1
    up = counts.get(C.TREND_UP, 0)
    down = counts.get(C.TREND_DOWN, 0)
    above = sum(1 for r in rows if r["above_ema"])
    fundings = [r["funding"] for r in rows if r["funding"] is not None]
    return {
        "regime_counts": counts,
        "pct_uptrend": round(up / n, 3),
        "pct_downtrend": round(down / n, 3),
        "pct_above_ema20": round(above / n, 3),
        "avg_funding": round(sum(fundings) / len(fundings), 6) if fundings else None,
        "breadth": "risk-on" if up > down else "risk-off" if down > up else "mixed",
    }


def _setups(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    # momentum leaders that are also trending up
    leaders = [r for r in rows if r["regime"] == C.TREND_UP and (r["momentum"] or 0) > 0.05]
    for r in leaders[:4]:
        out.append({"symbol": r["symbol"], "kind": "leader",
                    "note": f"trending up, +{r['momentum'] * 100:.0f}% momentum"})
    # funding extremes -> contrarian watch
    fr = sorted((r for r in rows if r["funding"] is not None), key=lambda r: r["funding"])
    for r in reversed(fr[-2:]):
        if r["funding"] > 0.0003:
            out.append({"symbol": r["symbol"], "kind": "crowded-long",
                        "note": f"funding {r['funding'] * 100:+.3f}% — contrarian-bearish watch"})
    for r in fr[:2]:
        if r["funding"] < -0.0003:
            out.append({"symbol": r["symbol"], "kind": "crowded-short",
                        "note": f"funding {r['funding'] * 100:+.3f}% — contrarian-bullish watch"})
    # oversold mean-reversion candidates
    for r in rows:
        if r["rsi"] is not None and r["rsi"] < 30 and r["regime"] in (C.RANGE, C.LOW_VOL_DRIFT):
            out.append({"symbol": r["symbol"], "kind": "oversold",
                        "note": f"RSI {r['rsi']:.0f} in a range — mean-revert watch"})
    return out[:12]
