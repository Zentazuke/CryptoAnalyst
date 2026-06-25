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

import math
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from analyst.commentary import generate_commentary
from analyst.config import DB_PATH, DEFAULT_TIMEFRAME
from analyst.ingestion.sentiment import SentimentClient
from analyst.features import compute_indicators, snapshot
from analyst.features.engine import INDICATOR_VERSION
from analyst.regime import calibrate, classify_latest, classify_series
from analyst.regime.derivatives import align_funding
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

# Local dev: allow the Vite frontend (any localhost port) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["GET"],
    allow_headers=["*"],
)


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


@app.get("/indicators/{symbol}")
def indicators(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
) -> dict:
    """Latest technical-indicator snapshot computed from stored candles."""
    rows = store().get_candles(symbol, timeframe)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")
    snap = snapshot(rows)
    snap["meta"]["last_candle"] = ms_to_iso(snap["meta"]["last_ts"])
    return {"symbol": symbol, "timeframe": timeframe, **snap}


@app.get("/microstructure/{symbol}")
def microstructure(
    symbol: str,
    limit: int = Query(default=1, ge=1, le=2000),
) -> dict:
    """Latest (or recent) market-microstructure snapshot(s) for a symbol."""
    rows = store().get_micro(symbol, limit=limit)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"no microstructure for {symbol} — run `python -m analyst.collect_micro`",
        )
    for r in rows:
        r["snapshot_time"] = ms_to_iso(r["ts"])
    return {"symbol": symbol, "count": len(rows), "snapshots": rows}


@app.get("/regime/{symbol}")
def regime(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
    limit: int = Query(default=1, ge=1, le=2000),
) -> dict:
    """Current (or recent) regime call(s) with confidence and reasons."""
    rows = store().get_candles(symbol, timeframe)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")
    results = classify_series(rows)
    recent = results[-limit:]
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "current": results[-1].model_dump(),
        "recent": [r.model_dump() for r in recent],
    }


@app.get("/regime/{symbol}/calibration")
def regime_calibration(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
    horizon: int = Query(default=12, ge=1, le=200),
) -> dict:
    """Backtest the classifier's calls vs forward outcomes (measured accuracy)."""
    rows = store().get_candles(symbol, timeframe)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")
    report = calibrate(rows, params={"horizon": horizon})
    return {"symbol": symbol, "timeframe": timeframe, **report}


@app.get("/sentiment/{symbol}")
def sentiment(symbol: str) -> dict:
    """Live sentiment from the sentiment engine, or {available: false} if offline."""
    with SentimentClient() as sc:
        bundle = sc.bundle(symbol)
    if bundle is None:
        return {"symbol": symbol, "available": False}
    return {"symbol": symbol, "available": True, **bundle}


@app.get("/commentary/{symbol}")
def commentary(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
) -> dict:
    """A written analyst note: what's happening, what it means, and an outlook."""
    rows = store().get_candles(symbol, timeframe)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")
    micro_rows = store().get_micro(symbol, limit=1)
    micro = micro_rows[0] if micro_rows else None
    with SentimentClient() as sc:
        sentiment_bundle = sc.bundle(symbol)
    funding_rows = store().get_funding(symbol)
    note = generate_commentary(
        rows, timeframe, micro=micro, sentiment=sentiment_bundle, funding_rows=funding_rows
    )
    return {"symbol": symbol, "timeframe": timeframe, "as_of": ms_to_iso(rows[-1]["ts"]), **note}


def _line(times: list[int], arr) -> list[dict]:
    """Pack an indicator array into [{time, value}], dropping NaN warmup points."""
    out = []
    for t, v in zip(times, arr):
        fv = float(v)
        if math.isfinite(fv):
            out.append({"time": t, "value": fv})
    return out


@app.get("/chart/{symbol}")
def chart(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
    limit: int = Query(default=500, ge=10, le=5000),
) -> dict:
    """Candles + full engine-computed indicator series for charting.

    All indicator values are produced by the Python engine (single source of
    truth); the client never recomputes technical analysis itself. Times are
    UTC seconds, as expected by lightweight-charts.
    """
    rows = store().get_candles(symbol, timeframe, limit=limit)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")

    times = [int(r["ts"] // 1000) for r in rows]
    series = compute_indicators(rows)

    candles = [
        {
            "time": t,
            "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"],
        }
        for t, r in zip(times, rows)
    ]
    volume = [{"time": t, "value": r["volume"]} for t, r in zip(times, rows)]

    overlays = {
        name: _line(times, series[name])
        for name in ("bb_upper", "bb_mid", "bb_lower", "ema_20", "sma_20")
    }
    panels = {
        name: _line(times, series[name])
        for name in (
            "rsi_14", "macd", "macd_signal", "macd_hist",
            "atr_14", "adx_14", "plus_di", "minus_di",
        )
    }

    # aligned funding series (causal forward-fill), if funding history exists
    funding_rows = store().get_funding(symbol)
    if funding_rows:
        aligned = align_funding([r["ts"] for r in rows], funding_rows)
        panels["funding"] = [
            {"time": t, "value": float(v)}
            for t, v in zip(times, aligned)
            if math.isfinite(v)
        ]

    checks = store().quality(symbol, limit=1)
    quality = checks[0] if checks else None

    regime_results = classify_series(rows)
    regime_series = [
        {"time": t, "label": r.label, "confidence": r.confidence}
        for t, r in zip(times, regime_results)
    ]
    # attach the current regime's historical reliability (calibration lift)
    regime_current = regime_results[-1].model_dump()
    cal = calibrate(rows, regime_results)
    regime_current["calibration"] = cal["per_label"].get(regime_current["label"])
    regime_current["calibration_horizon"] = cal["horizon"]

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "indicator_version": INDICATOR_VERSION,
        "source": rows[-1]["source"],
        "last_candle": ms_to_iso(rows[-1]["ts"]),
        "bars": len(rows),
        "candles": candles,
        "volume": volume,
        "overlays": overlays,
        "panels": panels,
        "regime": regime_series,
        "regime_current": regime_current,
        "quality": quality,
    }
