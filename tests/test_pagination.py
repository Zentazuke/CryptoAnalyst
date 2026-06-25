"""fetch_ohlcv_history pagination logic, served by a synthetic in-memory API."""
from __future__ import annotations

from analyst.ingestion.cryptocom import CryptoComSource

HOUR_MS = 3_600_000
START = 1_700_000_000_000
N = 1000  # synthetic full history length


def _full_history():
    return [
        {
            "t": START + i * HOUR_MS,
            "o": "100", "h": "101", "l": "99", "c": str(100 + i), "v": "1",
        }
        for i in range(N)
    ]


class PagedSource(CryptoComSource):
    """Overrides the HTTP layer to serve a synthetic paginated candlestick API."""

    def __init__(self):
        super().__init__(client=None)
        self._all = _full_history()

    def _get(self, path, params):  # type: ignore[override]
        count = params.get("count", 300)
        end_ts = params.get("end_ts")
        rows = [r for r in self._all if end_ts is None or r["t"] <= end_ts]
        rows = rows[-count:]  # most recent `count` at or before end_ts
        return {"code": 0, "result": {"data": rows, "instrument_name": params["instrument_name"]}}


def test_paginates_past_single_request_cap():
    src = PagedSource()
    candles, raws = src.fetch_ohlcv_history("BTC_USDT", "1h", total=800, page=300)
    assert len(candles) == 800
    # ascending, unique, contiguous tail of the synthetic history
    ts = [c.ts for c in candles]
    assert ts == sorted(ts)
    assert len(set(ts)) == 800
    assert ts[-1] == START + (N - 1) * HOUR_MS  # newest bar included
    assert len(raws) >= 3  # needed multiple pages


def test_stops_at_start_of_history():
    src = PagedSource()
    candles, _ = src.fetch_ohlcv_history("BTC_USDT", "1h", total=5000, page=300)
    assert len(candles) == N  # cannot exceed available history; no infinite loop
    assert candles[0].ts == START
