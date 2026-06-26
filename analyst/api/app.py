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
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from analyst.commentary import DEFAULT_HORIZON, generate_commentary
from analyst.config import DB_PATH, DEFAULT_TIMEFRAME
from analyst.outlook_calibration import calibrate_combined
from analyst.ingestion import make_source
from analyst.ingestion.sentiment import SentimentClient
from analyst.levels import key_levels
from analyst.microstructure import compute_microstructure
from analyst.scanner import scan_symbols

HIGHER_TF ={"1m": "15m", "5m": "1h", "15m": "1h", "30m": "4h", "1h": "4h", "4h": "1D", "12h": "1D", "1D": "7D"}
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


_live_cache: dict[tuple, tuple[float, list[dict]]] = {}


def _load_candles(symbol: str, timeframe: str, live_count: int = 1000) -> list[dict]:
    """Candles for a symbol: from the store if ingested, else fetched live.

    Lets the analyst cover any coin on demand (e.g. clicked from the scanner),
    not just the pre-ingested BTC/ETH. Live results are cached briefly.
    """
    rows = store().get_candles(symbol, timeframe)
    if rows:
        return rows

    key = (symbol, timeframe, live_count)
    now = time.time()
    cached = _live_cache.get(key)
    if cached and now - cached[0] < 60:
        return cached[1]

    src = make_source()
    try:
        candles, _ = src.fetch_ohlcv(symbol, timeframe, count=min(live_count, 1000))
    except Exception:
        candles = []
    finally:
        if hasattr(src, "close"):
            src.close()
    rows = [
        {"symbol": symbol, "timeframe": timeframe, "ts": c.ts,
         "open": c.open, "high": c.high, "low": c.low, "close": c.close,
         "volume": c.volume, "source": c.source, "ingest_ts": c.ingest_ts}
        for c in candles
    ]
    _live_cache[key] = (now, rows)
    return rows


_aux_cache: dict[tuple, tuple[float, Any]] = {}


def _cached(key: tuple, ttl: float, producer):
    """Tiny TTL memo for live aux fetches (funding/micro/positioning)."""
    now = time.time()
    hit = _aux_cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = producer()
    _aux_cache[key] = (now, value)
    return value


def _load_funding(symbol: str) -> list[dict]:
    """Funding history: stored if present, else live-fetched from the venue."""
    rows = store().get_funding(symbol)
    if rows:
        return rows

    def fetch():
        src = make_source()
        try:
            perp = src.perp_for(symbol) if hasattr(src, "perp_for") else None
            if perp and hasattr(src, "fetch_funding_history"):
                hist, _ = src.fetch_funding_history(perp, total=1000)
                return hist
        except Exception:
            pass
        finally:
            if hasattr(src, "close"):
                src.close()
        return []

    return _cached(("funding", symbol), 600, fetch)


def _load_micro(symbol: str) -> dict | None:
    """Latest microstructure: stored if present, else computed live (not stored)."""
    rows = store().get_micro(symbol, limit=1)
    if rows:
        return rows[0]

    def fetch():
        src = make_source()
        try:
            snap, _ = compute_microstructure(symbol, src)
            d = snap.model_dump()
            d["snapshot_time"] = ms_to_iso(snap.ts)
            d["live"] = True
            return d
        except Exception:
            return None
        finally:
            if hasattr(src, "close"):
                src.close()

    return _cached(("micro", symbol), 30, fetch)


def _htf_context(symbol: str, timeframe: str) -> dict | None:
    """Regime of the next-higher timeframe, for multi-timeframe context."""
    higher = HIGHER_TF.get(timeframe)
    if not higher:
        return None
    rows = _load_candles(symbol, higher)
    if len(rows) < 60:
        return None
    reg = classify_latest(rows)
    return {"timeframe": higher, "label": reg.label, "confidence": reg.confidence}


def _live_positioning(symbol: str) -> dict | None:
    """Live crowd long/short ratio for the native crowd read (any coin)."""
    def fetch():
        src = make_source()
        try:
            return src.fetch_lsr(symbol) if hasattr(src, "fetch_lsr") else None
        except Exception:
            return None
        finally:
            if hasattr(src, "close"):
                src.close()

    return _cached(("lsr", symbol), 120, fetch)


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
    rows = _load_candles(symbol, timeframe)
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
        live = _load_micro(symbol)  # compute one live (e.g. a coin clicked from the scan)
        if live:
            return {"symbol": symbol, "count": 1, "snapshots": [live]}
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
    rows = _load_candles(symbol, timeframe)
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


@app.get("/outlook-calibration/{symbol}")
def outlook_calibration(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
    horizon: int = Query(default=24, ge=1, le=200),
) -> dict:
    """Does confluence beat the parts? Measured lift for regime / htf / crowd /
    their agreement, on reconstructable history (live news-sentiment excluded)."""
    rows = _load_candles(symbol, timeframe)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")
    higher = HIGHER_TF.get(timeframe)
    htf_rows = _load_candles(symbol, higher) if higher else None
    rep = calibrate_combined(rows, _load_funding(symbol), htf_candles=htf_rows, horizon=horizon)
    if rep is None:
        raise HTTPException(status_code=422, detail="not enough history to calibrate")
    return {"symbol": symbol, "timeframe": timeframe, **rep}


@app.get("/regime/{symbol}/calibration")
def regime_calibration(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
    horizon: int = Query(default=12, ge=1, le=200),
) -> dict:
    """Backtest the classifier's calls vs forward outcomes (measured accuracy)."""
    rows = _load_candles(symbol, timeframe)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")
    report = calibrate(rows, params={"horizon": horizon})
    return {"symbol": symbol, "timeframe": timeframe, **report}


_scan_cache: dict[tuple, tuple[float, dict]] = {}


@app.get("/scan")
def scan(
    timeframe: str = Query(default="4h"),
    limit: int = Query(default=24, ge=4, le=60),
) -> dict:
    """Cross-asset market scan: per-coin regime + relative strength + funding."""
    key = (timeframe, limit)
    now = time.time()
    cached = _scan_cache.get(key)
    if cached and now - cached[0] < 300:  # 5-min cache (the sweep is heavy)
        return {**cached[1], "cached": True}

    source = make_source()
    if not hasattr(source, "fetch_top_symbols"):
        raise HTTPException(status_code=501, detail="scan requires the Binance source")
    try:
        symbols = source.fetch_top_symbols(limit=limit)
        result = scan_symbols(source, symbols, timeframe=timeframe)
    finally:
        if hasattr(source, "close"):
            source.close()
    _scan_cache[key] = (now, result)
    return {**result, "cached": False}


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
    rows = _load_candles(symbol, timeframe)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")
    micro = _load_micro(symbol)
    with SentimentClient() as sc:
        sentiment_bundle = sc.bundle(symbol)
    funding_rows = _load_funding(symbol)

    # crowd inputs: prefer the sentiment engine; else native (live LSR + funding)
    positioning = (sentiment_bundle.get("positioning") if sentiment_bundle else None) or _live_positioning(symbol)
    derivatives = sentiment_bundle.get("derivatives") if sentiment_bundle else None
    if not derivatives and micro and micro.get("funding_rate") is not None:
        derivatives = {"funding_rate": micro["funding_rate"], "open_interest_usd": micro.get("open_interest")}

    higher = HIGHER_TF.get(timeframe)
    htf_rows = _load_candles(symbol, higher) if higher else []
    htf = None
    if len(htf_rows) >= 60:
        hreg = classify_latest(htf_rows)
        htf = {"timeframe": higher, "label": hreg.label, "confidence": hreg.confidence}
    horizon = DEFAULT_HORIZON.get(timeframe, 12)
    outlook_cal = calibrate_combined(rows, funding_rows, htf_candles=htf_rows or None, horizon=horizon)

    note = generate_commentary(
        rows, timeframe, micro=micro, sentiment=sentiment_bundle, funding_rows=funding_rows,
        positioning=positioning, derivatives=derivatives, htf=htf, outlook_calibration=outlook_cal,
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
    rows = _load_candles(symbol, timeframe, live_count=limit)[-limit:]
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

    # aligned funding series (causal forward-fill); stored or live-fetched
    funding_rows = _load_funding(symbol)
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
        "levels": key_levels(rows),
        "quality": quality,
    }
