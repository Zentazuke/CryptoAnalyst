"""Explainability: every currently-fired signal WITH its measured track record.

The rule this module enforces (P1 of the 2026-07-04 upgrade plan): a directional
read is only as good as its receipts. For the latest bar, list each signal that
is currently calling a direction, joined to its calibration row — hit rate,
sample size, base rate, Wilson CI, significance, sub-period stability — so the
user (or a bot) can weigh every claim by its evidence. Signals without a
calibration row are labeled `uncalibrated` and must be treated as decoration.

Pure function over candles — no store, no network — so it is trivially testable
and reusable (API endpoint, frontend evidence panel, future composite score).
"""
from __future__ import annotations

from typing import Any

from analyst.ensemble import directional_signals
from analyst.signal_eval import _combinations, evaluate_signals

_STAT_KEYS = ("n", "accuracy", "base", "lift", "ci_low", "ci_high",
              "verdict", "significant", "stable", "reliable")


def explain_signals(candles: list[Any], timeframe: str, horizon: int | None = None) -> dict:
    """What is firing right now, and how much should you trust each claim?

    Returns {timeframe, horizon, fired: [...], summary: {...}} where each fired
    entry is a signal calling a direction on the LATEST bar, with its full
    calibration evidence attached. `fired` is sorted reliable-first, then by
    measured lift — the order a careful analyst would read them in.
    """
    report = evaluate_signals(candles, timeframe, horizon)
    stats = {r["signal"]: r for r in report["signals"]}

    sig = directional_signals(candles)
    sig.update(_combinations(sig))

    fired: list[dict] = []
    for name, arr in sig.items():
        v = float(arr[-1])
        if v == 0:
            continue
        entry: dict[str, Any] = {"signal": name,
                                 "direction": "bullish" if v > 0 else "bearish"}
        row = stats.get(name)
        if row:
            entry.update({k: row[k] for k in _STAT_KEYS})
        else:  # never fired on a significant historical move -> no evidence at all
            entry.update({"verdict": "uncalibrated", "significant": False,
                          "stable": False, "reliable": False})
        fired.append(entry)

    fired.sort(key=lambda r: (not r.get("reliable", False), -(r.get("lift") or 0.0)))

    rel_bull = sum(1 for f in fired if f["reliable"] and f["direction"] == "bullish")
    rel_bear = sum(1 for f in fired if f["reliable"] and f["direction"] == "bearish")
    if rel_bull and not rel_bear:
        read = "bullish"
    elif rel_bear and not rel_bull:
        read = "bearish"
    elif rel_bull and rel_bear:
        read = "mixed"
    else:
        read = "no-reliable-signal"
    return {
        "timeframe": report["timeframe"],
        "horizon": report["horizon"],
        "fired": fired,
        "summary": {
            "fired_total": len(fired),
            "reliable_bullish": rel_bull,
            "reliable_bearish": rel_bear,
            "read": read,
            "note": "Weigh only `reliable` rows (significant AND stable in both "
                    "sample halves). `uncalibrated`/unstable rows are context, not evidence.",
        },
    }
