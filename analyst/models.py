"""Domain models shared across ingestion, storage, and quality.

Every record that represents observed market data carries provenance:
`source` (who told us) and `ingest_ts` (when we recorded it). This is the
backbone of the trust layer — no number exists without knowing where it came
from and how fresh it is.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Candle(BaseModel):
    """A single OHLCV bar with provenance.

    `ts` is the candle's open time in milliseconds since the Unix epoch, as
    reported by the venue. `ingest_ts` is when *we* recorded it.
    """

    symbol: str
    timeframe: str
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    ingest_ts: int


class IngestResult(BaseModel):
    """Provenance record for one fetch+store batch."""

    source: str
    symbol: str
    timeframe: str
    fetched_ts: int
    rows: int
    raw_path: str
    status: str = "ok"


class MicroSnapshot(BaseModel):
    """A point-in-time market-microstructure snapshot with provenance.

    Spot fields (mid/spread/depth) come from the order book; derivatives fields
    (open interest, funding, mark/index, basis) come from the mapped perpetual
    and are ``None`` when no perp is mapped.
    """

    symbol: str
    ts: int
    mid: float
    best_bid: float
    best_ask: float
    spread_bps: float
    depth_band_bps: float
    bid_depth_base: float
    ask_depth_base: float
    bid_depth_quote: float
    ask_depth_quote: float
    open_interest: float | None = None
    funding_rate: float | None = None
    mark_price: float | None = None
    index_price: float | None = None
    basis_bps: float | None = None
    source: str
    ingest_ts: int


class GapReport(BaseModel):
    """Result of a gap check over a contiguous candle series.

    `missing` lists the expected open-times (ms) that were absent between the
    first and last observed candle.
    """

    symbol: str
    timeframe: str
    expected: int
    present: int
    missing: list[int] = Field(default_factory=list)

    @property
    def has_gaps(self) -> bool:
        return len(self.missing) > 0
