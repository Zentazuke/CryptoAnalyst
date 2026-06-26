"""Coin Metrics Community API (keyless) — free on-chain network data.

The free tier serves network-activity metrics (active addresses, transaction
count, price, market cap). Valuation metrics like realized cap / MVRV require a
paid key, so we build the on-chain read around *activity* and its divergence
from price — which is free and genuinely useful.
"""
from __future__ import annotations

from datetime import date, timedelta

import httpx

BASE = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
FREE_METRICS = ("AdrActCnt", "TxCnt", "PriceUSD", "CapMrktCurUSD")


class CoinMetricsSource:
    name = "coinmetrics"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 30.0) -> None:
        self._own = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._own:
            self._client.close()

    def fetch_metrics(self, asset: str, metrics: list[str], days: int = 240) -> list[dict]:
        """Daily metric rows for an asset, oldest-to-newest. Returns [] on failure."""
        start = (date.today() - timedelta(days=days)).isoformat()
        params = {
            "assets": asset.lower(),
            "metrics": ",".join(metrics),
            "frequency": "1d",
            "page_size": 10000,
            "start_time": start,
        }
        try:
            r = self._client.get(BASE, params=params)
            r.raise_for_status()
        except Exception:
            return []
        return r.json().get("data", [])
