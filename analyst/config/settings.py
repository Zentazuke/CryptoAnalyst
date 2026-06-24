"""Central configuration.

Paths can be overridden with environment variables so tests and alternate
deployments never collide with the default on-disk store:

    ANALYST_DATA_DIR   overrides the data directory (db + raw archive)
"""
from __future__ import annotations

import os
from pathlib import Path

# repo root = two levels up from this file (analyst/config/settings.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.environ.get("ANALYST_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "analyst.duckdb"

# Crypto.com Exchange public REST API (no auth needed for market data).
CRYPTOCOM_REST_BASE = "https://api.crypto.com/exchange/v1"

# Canonical timeframe -> seconds. Used for gap detection and cadence checks.
# Keys mirror Crypto.com's `timeframe` parameter values.
INTERVAL_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "12h": 43200,
    "1D": 86400,
    "7D": 604800,
    "14D": 1209600,
}

DEFAULT_SYMBOLS: list[str] = ["BTC_USDT", "ETH_USDT"]
DEFAULT_TIMEFRAME: str = "1h"
