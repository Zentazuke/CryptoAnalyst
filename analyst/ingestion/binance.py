"""Binance public-data source (no API key required).

Richer free data than most venues: up to 1000 klines/request, funding-rate
history, and open-interest history. Internal symbols use the ``BASE_QUOTE``
convention (e.g. ``BTC_USDT``); this adapter translates to Binance's
``BTCUSDT`` form. Spot market data comes from ``api.binance.com``; derivatives
(funding, mark/index, open interest) from the USDⓈ-M futures API
``fapi.binance.com`` (perp shares the spot symbol).
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

from analyst.models import Candle
from analyst.utils import now_ms

SPOT_BASE = "https://api.binance.com"
FUT_BASE = "https://fapi.binance.com"

# internal timeframe -> Binance interval
_TF = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "4h", "12h": "12h", "1D": "1d", "7D": "1w",
}
_DEPTH_ALLOWED = [5, 10, 20, 50, 100, 500, 1000, 5000]
_RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


class BinanceError(RuntimeError):
    pass


class BinanceSource:
    name = "binance"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 20.0) -> None:
        self._own_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._own_client:
            self._client.close()

    def __enter__(self) -> "BinanceSource":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _sym(symbol: str) -> str:
        return symbol.replace("_", "").upper()

    def perp_for(self, symbol: str) -> str:
        """Binance USDⓈ-M perp shares the spot symbol (BTC_USDT -> BTCUSDT)."""
        return self._sym(symbol)

    def _interval(self, timeframe: str) -> str:
        if timeframe not in _TF:
            raise BinanceError(f"unsupported timeframe {timeframe!r} for Binance")
        return _TF[timeframe]

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        reraise=True,
    )
    def _get(self, base: str, path: str, params: dict) -> object:
        resp = self._client.get(f"{base}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def _parse_klines(self, symbol: str, timeframe: str, rows: list, ingest_ts: int) -> list[Candle]:
        candles = [
            Candle(
                symbol=symbol, timeframe=timeframe, ts=int(r[0]),
                open=float(r[1]), high=float(r[2]), low=float(r[3]),
                close=float(r[4]), volume=float(r[5]),
                source=self.name, ingest_ts=ingest_ts,
            )
            for r in rows
        ]
        candles.sort(key=lambda c: c.ts)
        return candles

    # ---- OHLCV ------------------------------------------------------------

    def fetch_ohlcv(self, symbol: str, timeframe: str, count: int = 300) -> tuple[list[Candle], dict]:
        raw = self._get(
            SPOT_BASE, "/api/v3/klines",
            {"symbol": self._sym(symbol), "interval": self._interval(timeframe), "limit": min(count, 1000)},
        )
        candles = self._parse_klines(symbol, timeframe, raw, now_ms())
        return candles, {"klines": raw}

    def fetch_ohlcv_history(
        self, symbol: str, timeframe: str, total: int, page: int = 1000, pause: float = 0.1
    ) -> tuple[list[Candle], list[dict]]:
        bsym, interval = self._sym(symbol), self._interval(timeframe)
        collected: dict[int, Candle] = {}
        raws: list[dict] = []
        end_time: int | None = None
        max_pages = total // page + 6

        for _ in range(max_pages):
            if len(collected) >= total:
                break
            params: dict = {"symbol": bsym, "interval": interval, "limit": page}
            if end_time is not None:
                params["endTime"] = end_time
            rows = self._get(SPOT_BASE, "/api/v3/klines", params)
            if not rows:
                break
            raws.append({"klines": rows})
            candles = self._parse_klines(symbol, timeframe, rows, now_ms())
            new = sum(1 for c in candles if c.ts not in collected)
            for c in candles:
                collected.setdefault(c.ts, c)
            oldest = candles[0].ts
            next_end = oldest - 1
            if new == 0 or (end_time is not None and next_end >= end_time):
                break
            end_time = next_end
            time.sleep(pause)

        ordered = sorted(collected.values(), key=lambda c: c.ts)
        return (ordered[-total:] if len(ordered) > total else ordered), raws

    # ---- microstructure inputs -------------------------------------------

    def fetch_orderbook(self, symbol: str, depth: int = 50) -> tuple[dict, dict]:
        limit = next((a for a in _DEPTH_ALLOWED if a >= depth), 5000)
        raw = self._get(SPOT_BASE, "/api/v3/depth", {"symbol": self._sym(symbol), "limit": limit})
        bids = [[float(p), float(q)] for p, q in raw.get("bids", [])]
        asks = [[float(p), float(q)] for p, q in raw.get("asks", [])]
        return {"bids": bids, "asks": asks, "t": now_ms()}, raw

    def fetch_ticker(self, symbol: str) -> tuple[dict, dict]:
        bsym = self._sym(symbol)
        book = self._get(SPOT_BASE, "/api/v3/ticker/bookTicker", {"symbol": bsym})
        day = self._get(SPOT_BASE, "/api/v3/ticker/24hr", {"symbol": bsym})
        oi = None
        try:
            oi_raw = self._get(FUT_BASE, "/fapi/v1/openInterest", {"symbol": bsym})
            oi = float(oi_raw["openInterest"])
        except Exception:  # noqa: BLE001 - not all symbols have a perp
            oi = None
        parsed = {
            "instrument": bsym,
            "last": float(day["lastPrice"]),
            "bid": float(book["bidPrice"]),
            "ask": float(book["askPrice"]),
            "volume": float(day["volume"]),
            "oi": oi,
            "t": now_ms(),
        }
        return parsed, {"bookTicker": book, "ticker24hr": day}

    def fetch_valuation(self, symbol: str, valuation_type: str, count: int = 1) -> tuple[list[dict], dict]:
        """mark_price / index_price (from premiumIndex) and funding_hist (fundingRate)."""
        bsym = self._sym(symbol)
        if valuation_type in ("mark_price", "index_price"):
            raw = self._get(FUT_BASE, "/fapi/v1/premiumIndex", {"symbol": bsym})
            key = "markPrice" if valuation_type == "mark_price" else "indexPrice"
            return [{"t": int(raw.get("time", now_ms())), "v": float(raw[key])}], raw
        if valuation_type == "funding_hist":
            raw = self._get(FUT_BASE, "/fapi/v1/fundingRate", {"symbol": bsym, "limit": max(count, 1)})
            vals = [{"t": int(x["fundingTime"]), "v": float(x["fundingRate"])} for x in raw]
            vals.sort(key=lambda x: x["t"])
            return vals, {"fundingRate": raw}
        raise BinanceError(f"unsupported valuation_type {valuation_type!r}")

    def fetch_top_symbols(self, quote: str = "USDT", limit: int = 30) -> list[str]:
        """Top spot symbols by 24h quote volume (excludes stables + leveraged tokens)."""
        stable_bases = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "EUR", "GBP", "AEUR"}
        lev = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
        data = self._get(SPOT_BASE, "/api/v3/ticker/24hr", {})
        rows = []
        for t in data:
            s = t.get("symbol", "")
            if not s.endswith(quote) or s.endswith(lev):
                continue
            base = s[: -len(quote)]
            if base in stable_bases or base.startswith("USD"):  # USD1, USDC, ...
                continue
            try:
                rows.append((s, float(t["quoteVolume"])))
            except (KeyError, ValueError):
                continue
        rows.sort(key=lambda r: r[1], reverse=True)
        return [s for s, _ in rows[:limit]]

    def fetch_all_funding(self) -> dict[str, float]:
        """Current funding rate for every USDⓈ-M perp, keyed by symbol."""
        out: dict[str, float] = {}
        for x in self._get(FUT_BASE, "/fapi/v1/premiumIndex", {}):
            try:
                out[x["symbol"]] = float(x["lastFundingRate"])
            except (KeyError, ValueError, TypeError):
                continue
        return out

    def fetch_funding_history(
        self, perp: str, total: int, page: int = 1000, pause: float = 0.1
    ) -> tuple[list[dict], list[dict]]:
        """8h funding-rate history, paged endTime backwards."""
        collected: dict[int, float] = {}
        raws: list[dict] = []
        end_time: int | None = None
        max_pages = total // page + 6

        for _ in range(max_pages):
            if len(collected) >= total:
                break
            params: dict = {"symbol": perp, "limit": page}
            if end_time is not None:
                params["endTime"] = end_time
            rows = self._get(FUT_BASE, "/fapi/v1/fundingRate", params)
            if not rows:
                break
            raws.append({"fundingRate": rows})
            pts = [(int(x["fundingTime"]), float(x["fundingRate"])) for x in rows]
            new = sum(1 for t, _ in pts if t not in collected)
            for t, v in pts:
                collected.setdefault(t, v)
            oldest = min(t for t, _ in pts)
            next_end = oldest - 1
            if new == 0 or (end_time is not None and next_end >= end_time):
                break
            end_time = next_end
            time.sleep(pause)

        rows_out = [{"t": t, "v": v} for t, v in sorted(collected.items())]
        return (rows_out[-total:] if len(rows_out) > total else rows_out), raws
