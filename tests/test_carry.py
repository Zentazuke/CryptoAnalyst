"""Tests for the funding-carry read (synthetic)."""
from analyst.carry import carry_read


def _rows(rate, n=600, key="v"):
    return [{key: rate, "t": i * 28_800_000} for i in range(n)]


def test_none_on_short_history():
    assert carry_read(_rows(0.0001, n=50)) is None


def test_positive_funding_gives_positive_annual_carry():
    # 0.0001 per 8h * 3 * 365 = ~10.95% annual
    r = carry_read(_rows(0.0001))
    assert r is not None
    assert 10 < r["carry_annual_pct"] < 12
    assert r["samples"] == 600


def test_compression_flag():
    # recent funding lower than the long-run average -> compressing
    rows = _rows(0.0003, n=540) + _rows(0.00005, n=90)
    r = carry_read(rows)
    assert r["compressing"] is True


def test_accepts_funding_rate_key():
    r = carry_read(_rows(0.0002, key="funding_rate"))
    assert r is not None and r["carry_annual_pct"] > 0
