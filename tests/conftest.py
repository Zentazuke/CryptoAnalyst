"""Shared test fixtures: a deterministic, realistic OHLCV series."""
from __future__ import annotations

import numpy as np
import pytest

HOUR_MS = 3_600_000
START = 1_700_000_000_000


def _make_ohlc(n: int = 300, seed: int = 42) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, 0.01, n)
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.empty_like(close)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0, 0.003, n)))
    volume = rng.uniform(10.0, 100.0, n)
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


@pytest.fixture
def ohlc() -> dict[str, np.ndarray]:
    return _make_ohlc()


@pytest.fixture
def candles(ohlc) -> list[dict]:
    out = []
    n = len(ohlc["close"])
    for i in range(n):
        out.append(
            {
                "symbol": "BTC_USDT",
                "timeframe": "1h",
                "ts": START + i * HOUR_MS,
                "open": float(ohlc["open"][i]),
                "high": float(ohlc["high"][i]),
                "low": float(ohlc["low"][i]),
                "close": float(ohlc["close"][i]),
                "volume": float(ohlc["volume"][i]),
                "source": "test",
                "ingest_ts": START,
            }
        )
    return out
