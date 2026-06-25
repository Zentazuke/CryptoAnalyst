"""Select the active market-data source by name (config ``EXCHANGE``)."""
from __future__ import annotations

from analyst.config import EXCHANGE
from analyst.ingestion.binance import BinanceSource
from analyst.ingestion.cryptocom import CryptoComSource


def make_source(name: str | None = None):
    """Return a data source. ``name`` overrides the configured EXCHANGE."""
    key = (name or EXCHANGE).lower().replace(".", "").replace("-", "")
    if key == "binance":
        return BinanceSource()
    if key in ("cryptocom", "cryptocomexchange"):
        return CryptoComSource()
    raise ValueError(f"unknown exchange {name!r} (use 'binance' or 'cryptocom')")
