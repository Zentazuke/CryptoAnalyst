"""Deribit public API (keyless) — implied volatility (DVOL) for BTC/ETH."""
from __future__ import annotations

import time

import httpx

BASE = "https://www.deribit.com/api/v2/public"
SUPPORTED = {"BTC", "ETH"}


class DeribitSource:
    name = "deribit"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 15.0) -> None:
        self._own = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._own:
            self._client.close()

    def fetch_dvol(self, currency: str) -> float | None:
        """Latest DVOL (annualized implied-vol index, %) for BTC/ETH, or None."""
        cur = currency.upper()
        if cur not in SUPPORTED:
            return None
        now = int(time.time() * 1000)
        try:
            r = self._client.get(f"{BASE}/get_volatility_index_data", params={
                "currency": cur, "start_timestamp": now - 2 * 86_400_000,
                "end_timestamp": now, "resolution": 3600,
            })
            r.raise_for_status()
            data = (r.json().get("result") or {}).get("data", [])
            return float(data[-1][4]) if data else None  # [ts, o, h, l, close]
        except Exception:
            return None

    def fetch_dvol_history(self, currency: str, days: int = 1825,
                           resolution: int = 86400) -> list[dict]:
        """Historical DVOL closes for BTC/ETH — the enabler for backtesting the
        volatility risk premium. Paginates backward; returns [{ts, dvol}] oldest
        first. ``resolution`` is seconds per bar (86400 = daily)."""
        cur = currency.upper()
        if cur not in SUPPORTED:
            return []
        now = int(time.time() * 1000)
        start = now - days * 86_400_000
        collected: dict[int, float] = {}
        end = now
        for _ in range(days // 400 + 6):
            try:
                r = self._client.get(f"{BASE}/get_volatility_index_data", params={
                    "currency": cur, "start_timestamp": start,
                    "end_timestamp": end, "resolution": resolution,
                })
                r.raise_for_status()
                data = (r.json().get("result") or {}).get("data", [])
            except Exception:
                break
            if not data:
                break
            new = 0
            for row in data:
                t = int(row[0])
                if t not in collected:
                    collected[t] = float(row[4])
                    new += 1
            oldest = min(int(row[0]) for row in data)
            if new == 0 or oldest <= start:
                break
            end = oldest - 1
            time.sleep(0.1)
        return [{"ts": t, "dvol": v} for t, v in sorted(collected.items())]
