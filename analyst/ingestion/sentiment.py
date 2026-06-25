"""Client for the standalone sentiment engine (separate real-time service).

The analyst consumes the engine over HTTP as a live sentiment source. Every
call degrades gracefully: if the engine is offline or a field is missing, we
return ``None`` and the analyst simply omits sentiment — never errors.

Internal symbols use ``BTC_USDT``; the engine's routes use ``BTC-USDT``.
"""
from __future__ import annotations

from typing import Any

import httpx

from analyst.config import SENTIMENT_API_BASE


class SentimentClient:
    def __init__(self, base_url: str = SENTIMENT_API_BASE, timeout: float = 5.0,
                 client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._own = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._own:
            self._client.close()

    def __enter__(self) -> "SentimentClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _key(symbol: str) -> str:
        return symbol.replace("_", "-").upper()

    def _get(self, path: str) -> Any:
        r = self._client.get(f"{self.base_url}{path}")
        r.raise_for_status()
        return r.json()

    def available(self) -> bool:
        try:
            self._get("/health")
            return True
        except Exception:
            return False

    def bundle(self, symbol: str) -> dict | None:
        """Fetch the full sentiment picture for a symbol, or None if engine down.

        The /outlook payload already embeds context and positioning; we add the
        shock alerts and recent scored headlines.
        """
        key = self._key(symbol)
        try:
            outlook = self._get(f"/outlook/{key}")
        except Exception:
            return None  # engine offline -> analyst proceeds without sentiment

        out: dict[str, Any] = {
            "outlook": outlook,
            "context": outlook.get("context"),
            "positioning": outlook.get("positioning"),
            "direction_prob_6h": outlook.get("direction_prob_6h"),
        }

        def fetch(name: str, path: str, unwrap: str | None = None):
            try:
                data = self._get(path)
                out[name] = data.get(unwrap) if unwrap else data
            except Exception:
                out[name] = None

        fetch("snapshot", f"/snapshot/{key}")          # sentiment activity metrics
        fetch("insights", f"/insights/{key}")          # trending terms + source split
        fetch("derivatives", f"/derivatives/{key}", unwrap="derivatives")
        fetch("alerts", f"/alerts/{key}")
        fetch("recent", f"/social/{key}/recent?limit=6")
        return out
