"""FastAPI app exposing read-only access to the store.

Endpoints (A0):
    GET /health                  store reachability + per-symbol freshness
    GET /provenance/{symbol}     where each series came from + when ingested
    GET /candles/{symbol}        recent OHLCV bars
    GET /quality/{symbol}        recent data-quality check results

A read-only DuckDB connection is opened for the app's lifetime. Run with:
    uvicorn analyst.api.app:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from analyst.config import DB_PATH, DEFAULT_TIMEFRAME
from analyst.storage import Store
from analyst.utils import ms_to_iso, now_ms

_store: Store | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store
    _store = Store(DB_PATH, read_only=True)
    try:
        yield
    finally:
        _store.close()
        _store = None


app = FastAPI(title="Crypto Analyst", version="0.1.0", lifespan=lifespan)


def store() -> Store:
    if _store is None:  # pragma: no cover - guarded by lifespan
        raise HTTPException(status_code=503, detail="store not initialised")
    return _store


@app.get("/health")
def health() -> dict:
    s = store()
    cur = s.conn.execute(
        "SELECT symbol, MAX(ts) AS last_ts, MAX(ingest_ts) AS last_ingest_ts "
        "FROM ohlcv GROUP BY symbol ORDER BY symbol"
    )
    cols = [d[0] for d in cur.description]
    symbols = []
    for row in cur.fetchall():
        rec = dict(zip(cols, row))
        symbols.append(
            {
                "symbol": rec["symbol"],
                "last_candle": ms_to_iso(rec["last_ts"]),
                "last_ingest": ms_to_iso(rec["last_ingest_ts"]),
            }
        )
    return {"status": "ok", "db": s.db_path, "now": ms_to_iso(now_ms()), "symbols": symbols}


@app.get("/provenance/{symbol}")
def provenance(symbol: str) -> dict:
    prov = store().provenance(symbol)
    if not prov["series"]:
        raise HTTPException(status_code=404, detail=f"no data for {symbol}")
    for s in prov["series"]:
        s["first_candle"] = ms_to_iso(s["first_ts"])
        s["last_candle"] = ms_to_iso(s["last_ts"])
        s["last_ingest"] = ms_to_iso(s["last_ingest_ts"])
    return prov


@app.get("/candles/{symbol}")
def candles(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
    limit: int = Query(default=200, ge=1, le=5000),
) -> dict:
    rows = store().get_candles(symbol, timeframe, limit=limit)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")
    return {"symbol": symbol, "timeframe": timeframe, "count": len(rows), "candles": rows}


@app.get("/quality/{symbol}")
def quality(symbol: str, limit: int = Query(default=20, ge=1, le=200)) -> dict:
    return {"symbol": symbol, "checks": store().quality(symbol, limit=limit)}
