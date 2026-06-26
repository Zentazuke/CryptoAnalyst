"""On-chain snapshot: divergence detection (offline fake source)."""
from __future__ import annotations

from analyst.onchain import onchain_snapshot


class FakeCM:
    """Addresses rising, price falling -> bullish divergence."""

    def __init__(self, addr_up=True, price_down=True):
        self.addr_up, self.price_down = addr_up, price_down

    def fetch_metrics(self, asset, metrics, days=240):
        rows = []
        for i in range(120):
            addr = 100_000 + (i * 500 if self.addr_up else -i * 500)
            price = 100.0 - (i * 0.3 if self.price_down else -i * 0.3)
            rows.append({"asset": asset, "time": f"2026-01-{i:03d}",
                         "AdrActCnt": str(addr), "TxCnt": str(200_000 + i * 100), "PriceUSD": str(max(price, 1.0))})
        return rows


def test_bullish_divergence():
    snap = onchain_snapshot("BTC_USDT", source=FakeCM(addr_up=True, price_down=True))
    assert snap is not None
    assert snap["divergence"] == "bullish"
    assert snap["addr_trend_30d"] > 0 and snap["price_trend_30d"] < 0


def test_bearish_divergence():
    snap = onchain_snapshot("BTC_USDT", source=FakeCM(addr_up=False, price_down=False))
    assert snap["divergence"] == "bearish"


def test_none_when_no_data():
    class Empty:
        def fetch_metrics(self, *a, **k):
            return []
    assert onchain_snapshot("XYZ_USDT", source=Empty()) is None
