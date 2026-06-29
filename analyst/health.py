"""Data-health assessment (pure functions, easy to test).

The engine should fail *loud*: if a feed goes stale or the collector starts
erroring, that must be visible rather than silently served as if current. These
helpers turn raw timestamps + scheduler counters into a clear status the API and
dashboard can show.
"""
from __future__ import annotations

STALE_FACTOR = 2.5  # a feed is "stale" once it's older than this x its interval


def freshness(last_ts_ms: int | None, interval_s: int, now_ms: int,
              stale_factor: float = STALE_FACTOR) -> dict:
    """Age of a feed and whether it counts as stale."""
    if last_ts_ms is None:
        return {"age_seconds": None, "stale": True}
    age = max(0.0, (now_ms - last_ts_ms) / 1000.0)
    return {"age_seconds": round(age), "stale": age > interval_s * stale_factor}


def overall_status(freshness_items: list[dict], scheduler_errors: int = 0) -> str:
    """Roll per-feed freshness + collector errors into one status.

    "stale"    at least one feed is stale (most serious — acting on old data)
    "degraded" feeds are fresh but the collector is erroring
    "ok"       everything fresh and the collector healthy
    """
    if any(f.get("stale") for f in freshness_items):
        return "stale"
    if scheduler_errors > 0:
        return "degraded"
    return "ok"
