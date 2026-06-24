"""Crypto.com Exchange public-REST data source.

Uses the unauthenticated market-data endpoints. Candlestick response shape
(verified against the live API):

    {
      "code": 0,
      "result": {
        "instrument_name": "BTC_USDT",
        "interval": "1h",
        "data": [ {"o","h","l","c","v","t"}, ... ]   # t = ms epoch, OHLCV strings
      }
    }
"""
from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from analyst.config import CRYPTOCOM_REST_BASE
from analyst.models import Candle
from analyst.utils import now_ms

_RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


class CryptoComError(RuntimeError):
    """Raised when the API returns a non-success code or malformed payload."""


class CryptoComSource:
    """Fetches OHLCV from the Crypto.com Exchange public REST API."""

    name = "crypto.com"

    def __init__(
        self,
        base_url: str = CRYPTOCOM_REST_BASE,
        client: httpx.Client | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._own_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._own_client:
            self._client.close()

    def __enter__(self) -> "CryptoComSource":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        reraise=True,
    )
    def _get(self, path: str, params: dict) -> dict:
        resp = self._client.get(f"{self.base_url}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, count: int = 300
    ) -> tuple[list[Candle], dict]:
        raw = self._get(
            "/public/get-candlestick",
            {"instrument_name": symbol, "timeframe": timeframe, "count": count},
        )

        if raw.get("code") not in (0, "0"):
            raise CryptoComError(f"API error for {symbol}/{timeframe}: code={raw.get('code')}")

        result = raw.get("result") or {}
        rows = result.get("data") or []
        ingest_ts = now_ms()

        candles = [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                ts=int(row["t"]),
                open=float(row["o"]),
                high=float(row["h"]),
                low=float(row["l"]),
                close=float(row["c"]),
                volume=float(row["v"]),
                source=self.name,
                ingest_ts=ingest_ts,
            )
            for row in rows
        ]
        candles.sort(key=lambda c: c.ts)
        return candles, raw
