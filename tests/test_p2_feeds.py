"""P2 feeds: extraction correctness on canned payloads, graceful failure on junk."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from analyst.p2_feeds import (_parse_expiry_ms, derivs_crowd, options_surface,
                              stable_supply)

NOW = int(datetime(2026, 7, 4, tzinfo=timezone.utc).timestamp() * 1000)


def _exp_name(days: int) -> str:
    d = datetime(2026, 7, 4, tzinfo=timezone.utc) + timedelta(days=days)
    return d.strftime("%d%b%y").upper().lstrip("0")


def _opt(days, strike, typ, iv, under=100_000.0):
    return {"instrument_name": f"BTC-{_exp_name(days)}-{int(strike)}-{typ}",
            "mark_iv": iv, "underlying_price": under}


def test_parse_expiry():
    ms = _parse_expiry_ms("BTC-26SEP25-100000-C")
    d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    assert (d.year, d.month, d.day, d.hour) == (2025, 9, 26, 8)
    assert _parse_expiry_ms("garbage") is None


def test_options_surface_extraction():
    board = [
        # near expiry (~30d): ATM 50, put wing 55 @ 90%, call wing 48 @ 110%
        _opt(30, 100_000, "C", 50.0), _opt(30, 100_000, "P", 50.2),
        _opt(30, 90_000, "P", 55.0), _opt(30, 110_000, "C", 48.0),
        # far expiry (~90d): ATM 58
        _opt(90, 100_000, "C", 58.0), _opt(90, 100_000, "P", 58.1),
        # expiring in 2 days -> must be ignored
        _opt(2, 100_000, "C", 99.0),
        # dead quote -> ignored
        {"instrument_name": f"BTC-{_exp_name(30)}-120000-C", "mark_iv": None,
         "underlying_price": 100_000.0},
    ]
    surf = options_surface("BTC", get_json=lambda url: {"result": board}, now_ms=NOW)
    assert surf is not None
    assert surf["atm_iv_near"] in (50.0, 50.2)          # nearest-to-ATM quote
    assert surf["atm_iv_far"] in (58.0, 58.1)
    assert abs(surf["term_slope"] - (surf["atm_iv_far"] - surf["atm_iv_near"])) < 1e-9
    assert surf["rr_10pct"] == round(55.0 - 48.0, 3)    # put fear premium
    assert 25 <= surf["days_near"] <= 35
    assert surf["n_instruments"] == 6.0                  # 2d + dead quote excluded


def test_options_surface_empty_and_error():
    assert options_surface("BTC", get_json=lambda url: {"result": []}) is None
    def boom(url):
        raise RuntimeError("down")
    assert options_surface("BTC", get_json=boom) is None


def test_derivs_crowd_extraction():
    def fake(url):
        if "takerlongshort" in url:
            return [{"buySellRatio": "1.13"}]
        if "topLongShortAccountRatio" in url:
            return [{"longShortRatio": "2.4"}]
        if "openInterestHist" in url:
            return [{"sumOpenInterestValue": "1000000"},
                    {"sumOpenInterestValue": "1050000"}]
        raise AssertionError(url)
    d = derivs_crowd("BTC_USDT", get_json=fake)
    assert d["taker_buy_sell_ratio"] == 1.13
    assert d["top_ls_account_ratio"] == 2.4
    assert d["oi_usd"] == 1_050_000.0
    assert abs(d["oi_change_1h_pct"] - 5.0) < 1e-9


def test_derivs_crowd_partial_failure_still_returns():
    def flaky(url):
        if "takerlongshort" in url:
            return [{"buySellRatio": "0.9"}]
        raise RuntimeError("endpoint down")
    d = derivs_crowd("ETH_USDT", get_json=flaky)
    assert d == {"taker_buy_sell_ratio": 0.9}
    def all_down(url):
        raise RuntimeError("down")
    assert derivs_crowd("ETH_USDT", get_json=all_down) is None


def test_stable_supply_extraction():
    payload = {"peggedAssets": [
        {"symbol": "USDT", "circulating": {"peggedUSD": 120e9}},
        {"symbol": "USDC", "circulating": {"peggedUSD": 35e9}},
        {"symbol": "DAI", "circulating": {"peggedUSD": 5e9}},
        {"symbol": "BROKEN", "circulating": {}},
    ]}
    s = stable_supply(get_json=lambda url: payload)
    assert s["usdt_circulating"] == 120e9
    assert s["usdc_circulating"] == 35e9
    assert s["majors_circulating"] == 155e9
    assert s["total_stable_circulating"] == 160e9
    assert stable_supply(get_json=lambda url: {"peggedAssets": []}) is None
