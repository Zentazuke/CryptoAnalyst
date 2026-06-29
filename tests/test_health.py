"""Tests for the data-health assessment helpers."""
from analyst.health import freshness, overall_status

HOUR = 3600
MS = 1000


def test_fresh_feed_not_stale():
    now = 1_000_000 * MS
    f = freshness(now - 10 * MS, HOUR, now)  # 10s old, 1h interval
    assert f["stale"] is False and f["age_seconds"] == 10


def test_old_feed_is_stale():
    now = 1_000_000 * MS
    f = freshness(now - 5 * HOUR * MS, HOUR, now)  # 5h old > 2.5x1h
    assert f["stale"] is True and f["age_seconds"] == 5 * HOUR


def test_missing_feed_is_stale():
    f = freshness(None, HOUR, 1_000_000 * MS)
    assert f["stale"] is True and f["age_seconds"] is None


def test_overall_status_priority():
    fresh = {"stale": False}
    stale = {"stale": True}
    assert overall_status([fresh, fresh], 0) == "ok"
    assert overall_status([fresh, fresh], 3) == "degraded"
    assert overall_status([fresh, stale], 0) == "stale"
    assert overall_status([stale], 5) == "stale"  # stale outranks degraded
    assert overall_status([], 0) == "ok"
