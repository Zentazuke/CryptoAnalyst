"""The data-source contract.

Every venue/vendor adapter implements :class:`DataSource`. Returning the raw
payload alongside parsed candles lets the orchestrator archive exactly what the
source said, byte-for-byte, for later replay and audit.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from analyst.models import Candle


@runtime_checkable
class DataSource(Protocol):
    """A market-data source.

    Implementations must set a stable ``name`` (used as the provenance tag) and
    implement :meth:`fetch_ohlcv`.
    """

    name: str

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, count: int = 300
    ) -> tuple[list[Candle], dict]:
        """Fetch recent OHLCV bars.

        Returns ``(candles, raw_payload)`` where ``candles`` are parsed,
        provenance-stamped, and sorted ascending by ``ts``, and ``raw_payload``
        is the source's untouched JSON response for archival.
        """
        ...
