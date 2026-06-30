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

# Load .env (if present) so secrets/config live outside the code. Best-effort:
# python-dotenv ships as a transitive dependency; if absent we just skip.
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:  # pragma: no cover - optional
    pass

# Binance SPOT testnet credentials — only used by the future bot/execution
# layer. The analyst's data comes from free public endpoints and needs no key.
BINANCE_TESTNET: bool = os.environ.get("BINANCE_TESTNET", "false").lower() == "true"
BINANCE_TESTNET_API_KEY: str | None = os.environ.get("BINANCE_TESTNET_API_KEY")
BINANCE_TESTNET_API_SECRET: str | None = os.environ.get("BINANCE_TESTNET_API_SECRET")

DATA_DIR = Path(os.environ.get("ANALYST_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "analyst.duckdb"

# Active market-data exchange: "binance" (default) or "cryptocom".
EXCHANGE: str = os.environ.get("ANALYST_EXCHANGE", "binance").lower()

# Sentiment engine API (separate real-time service). The analyst consumes it as
# a live sentiment source and degrades gracefully when it is offline.
SENTIMENT_API_BASE: str = os.environ.get("SENTIMENT_API_BASE", "http://127.0.0.1:8787")

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

# Background scheduler (in-process collector). Off by default so tests and a
# plain `uvicorn` run stay read-only; the launchers set ANALYST_SCHEDULER=1 to
# turn the API into an always-on, self-feeding service.
SCHEDULER_ENABLED: bool = os.environ.get("ANALYST_SCHEDULER", "0").lower() in ("1", "true", "yes")
SCHEDULER_SYMBOLS: list[str] = [
    s.strip() for s in os.environ.get("ANALYST_SCHEDULER_SYMBOLS", "BTC_USDT,ETH_USDT,ROBO_USDC").split(",") if s.strip()
]
SCHEDULER_TIMEFRAMES: list[str] = [
    t.strip() for t in os.environ.get("ANALYST_SCHEDULER_TIMEFRAMES", "1h,4h,1D").split(",") if t.strip()
]
# Per-task cadence, in seconds.
SCHEDULER_INTERVALS: dict[str, int] = {
    "candles": int(os.environ.get("ANALYST_SCHED_CANDLES_S", 300)),    # refresh recent bars
    "microstructure": int(os.environ.get("ANALYST_SCHED_MICRO_S", 120)),  # accrue order-book history
    "funding": int(os.environ.get("ANALYST_SCHED_FUNDING_S", 1800)),   # funding history
    "alert_journal": int(os.environ.get("ANALYST_SCHED_JOURNAL_S", 900)),  # record fired alerts
    "vrp_journal": int(os.environ.get("ANALYST_SCHED_VRP_S", 21600)),  # daily VRP signal (deduped)
}

# Map a spot symbol to its perpetual instrument on Crypto.com, used to source
# open interest, funding, mark/index price, and basis. Spot symbols without a
# perp mapping simply get null derivatives fields.
PERP_FOR: dict[str, str] = {
    "BTC_USDT": "BTCUSD-PERP",
    "ETH_USDT": "ETHUSD-PERP",
}

# Default order-book band (in basis points around mid) for depth aggregation.
DEPTH_BAND_BPS: float = 10.0

