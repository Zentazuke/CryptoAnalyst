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

import time

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
        candles = self._parse_candles(symbol, timeframe, rows, now_ms())
        return candles, raw

    def _parse_candles(
        self, symbol: str, timeframe: str, rows: list[dict], ingest_ts: int
    ) -> list[Candle]:
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
        return candles

    def fetch_ohlcv_history(
        self,
        symbol: str,
        timeframe: str,
        total: int,
        page: int = 300,
        pause: float = 0.12,
    ) -> tuple[list[Candle], list[dict]]:
        """Fetch up to ``total`` candles by paging ``end_ts`` backwards.

        The API caps a single request at ~300 candles, so we walk backwards
        from the most recent bar. Returns ``(candles_ascending, raw_pages)``;
        de-duplicates on timestamp and stops at the start of available history.
        """
        collected: dict[int, Candle] = {}
        raws: list[dict] = []
        end_ts: int | None = None
        max_pages = total // page + 6

        for _ in range(max_pages):
            if len(collected) >= total:
                break
            params: dict = {"instrument_name": symbol, "timeframe": timeframe, "count": page}
            if end_ts is not None:
                params["end_ts"] = end_ts
            raw = self._get("/public/get-candlestick", params)
            if raw.get("code") not in (0, "0"):
                raise CryptoComError(f"API error for {symbol}/{timeframe}: code={raw.get('code')}")
            rows = (raw.get("result") or {}).get("data") or []
            if not rows:
                break
            raws.append(raw)

            page_candles = self._parse_candles(symbol, timeframe, rows, now_ms())
            new = sum(1 for c in page_candles if c.ts not in collected)
            for c in page_candles:
                collected.setdefault(c.ts, c)

            oldest = page_candles[0].ts
            next_end = oldest - 1
            if new == 0 or (end_ts is not None and next_end >= end_ts):
                break  # no progress -> reached start of history
            end_ts = next_end
            time.sleep(pause)

        candles = sorted(collected.values(), key=lambda c: c.ts)
        return (candles[-total:] if len(candles) > total else candles), raws

    def _check(self, raw: dict, what: str) -> dict:
        if raw.get("code") not in (0, "0"):
            raise CryptoComError(f"API error for {what}: code={raw.get('code')}")
        return raw.get("result") or {}

    def fetch_orderbook(self, symbol: str, depth: int = 50) -> tuple[dict, dict]:
        """Order-book snapshot. Returns ({bids, asks, t}, raw).

        ``bids``/``asks`` are lists of ``[price, size]`` floats; bids descend in
        price, asks ascend, as the venue returns them.
        """
        raw = self._get(
            "/public/get-book", {"instrument_name": symbol, "depth": depth}
        )
        data = (self._check(raw, f"book {symbol}").get("data") or [{}])[0]
        bids = [[float(p), float(s)] for p, s, *_ in data.get("bids", [])]
        asks = [[float(p), float(s)] for p, s, *_ in data.get("asks", [])]
        return {"bids": bids, "asks": asks, "t": int(data["t"])}, raw

    def fetch_funding_history(
        self, perp: str, total: int, page: int = 300, pause: float = 0.12
    ) -> tuple[list[dict], list[dict]]:
        """Hourly funding-rate history for a perpetual, paged ``end_ts`` backwards.

        Returns ``([{t, v}, ...] ascending, raw_pages)``."""
        collected: dict[int, float] = {}
        raws: list[dict] = []
        end_ts: int | None = None
        max_pages = total // page + 6

        for _ in range(max_pages):
            if len(collected) >= total:
                break
            params: dict = {"instrument_name": perp, "valuation_type": "funding_hist", "count": page}
            if end_ts is not None:
                params["end_ts"] = end_ts
            raw = self._get("/public/get-valuations", params)
            if raw.get("code") not in (0, "0"):
                raise CryptoComError(f"funding API error {perp}: code={raw.get('code')}")
            data = (raw.get("result") or {}).get("data") or []
            if not data:
                break
            raws.append(raw)
            pts = [(int(x["t"]), float(x["v"])) for x in data]
            new = sum(1 for t, _ in pts if t not in collected)
            for t, v in pts:
                collected.setdefault(t, v)
            oldest = min(t for t, _ in pts)
            next_end = oldest - 1
            if new == 0 or (end_ts is not None and next_end >= end_ts):
                break
            end_ts = next_end
            time.sleep(pause)

        rows = [{"t": t, "v": v} for t, v in sorted(collected.items())]
        return (rows[-total:] if len(rows) > total else rows), raws

    def fetch_ticker(self, symbol: str) -> tuple[dict, dict]:
        """Ticker snapshot. Returns (parsed, raw) with best bid/ask, last,
        volume, and open interest (``oi``; ``None`` for spot)."""
        raw = self._get("/public/get-tickers", {"instrument_name": symbol})
        t = (self._check(raw, f"ticker {symbol}").get("data") or [{}])[0]

        def f(key: str) -> float | None:
            v = t.get(key)
            return float(v) if v not in (None, "") else None

        parsed = {
            "instrument": t.get("i"),
            "last": f("a"),
            "bid": f("b"),
            "ask": f("k"),
            "volume": f("v"),
            "oi": f("oi"),
            "t": int(t["t"]),
        }
        return parsed, raw

    def fetch_valuation(
        self, symbol: str, valuation_type: str, count: int = 1
    ) -> tuple[list[dict], dict]:
        """Valuation series (mark_price, index_price, funding_hist, ...).

        Returns (list of {t, v}, raw), oldest-to-newest."""
        raw = self._get(
            "/public/get-valuations",
            {"instrument_name": symbol, "valuation_type": valuation_type, "count": count},
        )
        data = self._check(raw, f"valuation {valuation_type} {symbol}").get("data") or []
        vals = [{"t": int(x["t"]), "v": float(x["v"])} for x in data]
        vals.sort(key=lambda x: x["t"])
        return vals, raw
