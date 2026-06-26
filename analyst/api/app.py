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
from analyst.metric_reads import metric_reads
from analyst.config import DB_PATH, DEFAULT_TIMEFRAME, INTERVAL_SECONDS
from analyst.outlook_calibration import calibrate_combined
from analyst.ingestion import make_source
from analyst.ingestion.sentiment import SentimentClient
from analyst.levels import key_levels
from analyst.alert_calibration import aggregate_track_records, calibrate_alerts
from analyst.alerts import detect_alerts
from analyst.microstructure import compute_microstructure
from analyst.onchain import onchain_snapshot
from analyst.scanner import scan_symbols
from analyst.storage.journal import AlertJournal
from analyst.vol import implied_vol_context

_journal: AlertJournal | None = None


def journal() -> AlertJournal | None:
    global _journal
    if _journal is None:
        try:
            _journal = AlertJournal()
        except Exception:
            return None
    return _journal

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


def _live_fetch(symbol: str, timeframe: str, count: int = 1000) -> list[dict]:
    """Fetch recent candles live from the venue (cached ~60s)."""
    key = (symbol, timeframe, count)
    now = time.time()
    cached = _live_cache.get(key)
    if cached and now - cached[0] < 60:
        return cached[1]
    src = make_source()
    try:
        candles, _ = src.fetch_ohlcv(symbol, timeframe, count=min(count, 1000))
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


def _load_candles(symbol: str, timeframe: str, live_count: int = 1000) -> list[dict]:
    """Candles for a symbol: stored history kept fresh with live bars.

    Covers any coin on demand (not just pre-ingested BTC/ETH), and when the
    stored data goes stale it merges in fresh live bars — so the view stays
    current without a background writer (which would fight the DB lock).
    """
    rows = store().get_candles(symbol, timeframe)
    if not rows:
        return _live_fetch(symbol, timeframe, live_count)

    interval_ms = INTERVAL_SECONDS.get(timeframe, 3600) * 1000
    if rows[-1]["ts"] >= now_ms() - int(1.5 * interval_ms):
        return rows  # fresh enough

    live = _live_fetch(symbol, timeframe, live_count)  # stale -> merge fresh bars onto history
    if not live:
        return rows
    merged = {r["ts"]: r for r in rows}
    for r in live:
        merged[r["ts"]] = r
    return sorted(merged.values(), key=lambda r: r["ts"])


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


# Order-book state is point-in-time: a stored snapshot is only trustworthy while
# it is recent and complete. Older than this, we recompute live instead.
MICRO_STORED_MAX_AGE_S = 90


def _micro_is_fresh(row: dict, max_age_s: int = MICRO_STORED_MAX_AGE_S) -> bool:
    """A stored snapshot is usable only if it's recent and has the core fields."""
    ts = row.get("ts")
    if not ts or row.get("mid") is None or row.get("spread_bps") is None:
        return False
    return 0 <= time.time() - ts / 1000.0 <= max_age_s


def _load_micro(symbol: str) -> dict | None:
    """Latest microstructure: a *fresh* stored snapshot if we have one, otherwise
    a live order-book read (cached ~30s). A stale stored row is worse than
    useless for point-in-time book state, so we never surface it as current."""
    rows = store().get_micro(symbol, limit=1)
    if rows and _micro_is_fresh(rows[0]):
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


def _load_onchain(symbol: str) -> dict | None:
    """On-chain network-activity snapshot (cached ~1h; daily data)."""
    return _cached(("onchain", symbol), 3600, lambda: onchain_snapshot(symbol))


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
    """Latest (or recent) market-microstructure snapshot(s) for a symbol.

    For the latest snapshot (limit=1, what the card uses) we go through the
    freshness gate: a recent stored row is returned as-is, otherwise a live
    order-book read is computed — never a stale point-in-time row. For history
    (limit>1) we return the stored rows directly.
    """
    if limit == 1:
        snap = _load_micro(symbol)
        if snap:
            if not snap.get("snapshot_time") and snap.get("ts"):
                snap["snapshot_time"] = ms_to_iso(snap["ts"])
            return {"symbol": symbol, "count": 1, "snapshots": [snap]}
        raise HTTPException(
            status_code=404,
            detail=f"no microstructure for {symbol} — run `python -m analyst.collect_micro`",
        )

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


@app.get("/onchain/{symbol}")
def onchain(symbol: str) -> dict:
    """On-chain network activity (free Coin Metrics data), or {available: false}."""
    snap = _load_onchain(symbol)
    if not snap:
        return {"symbol": symbol, "available": False}
    return {"symbol": symbol, "available": True, **snap}


def _alert_track_record() -> dict:
    """Per-alert-type historical track record (aggregated over BTC/ETH, cached)."""
    def fetch():
        reps = []
        for sym in ("BTC_USDT", "ETH_USDT"):
            rows = store().get_candles(sym, "4h")
            if rows:
                reps.append(calibrate_alerts(rows, store().get_funding(sym), horizon=12))
        return aggregate_track_records(reps)

    return _cached(("alert_tr",), 3600, fetch)


def _cal_type(alert: dict) -> str:
    if alert["kind"] == "rsi-extreme":
        return "rsi-oversold" if alert["direction"] == "bull" else "rsi-overbought"
    return alert["kind"]


@app.get("/alerts")
def alerts(
    timeframe: str = Query(default="4h"),
    limit: int = Query(default=24, ge=4, le=60),
) -> dict:
    """Confluence-ranked setups across the scanned market, each with its measured
    track record (so you know which setup types historically have edge)."""
    result = scan(timeframe=timeframe, limit=limit)  # cached
    track = _alert_track_record()
    found = detect_alerts(result["rows"])
    for a in found:
        a["track_record"] = track.get(_cal_type(a))
    j = journal()
    if j:
        try:
            j.record(found, timeframe)
        except Exception:
            pass
    return {"timeframe": timeframe, "breadth": result["aggregates"]["breadth"], "alerts": found}


@app.get("/alert-journal")
def alert_journal_feed(limit: int = Query(default=60, ge=1, le=300)) -> dict:
    """Recently journaled alerts with their since-fired outcome + a live hit rate."""
    j = journal()
    if not j:
        return {"count": 0, "on_track_rate": None, "alerts": []}
    rows = j.recent(limit)
    try:  # current prices from the cached market scan (one call, no per-symbol fetches)
        price_map = {r["symbol"]: r["price"] for r in scan(timeframe="4h")["rows"]}
    except Exception:
        price_map = {}
    out = []
    for r in rows:
        cp = price_map.get(r["symbol"])
        ret = (cp - r["price_at_fire"]) / r["price_at_fire"] if cp and r["price_at_fire"] else None
        on_track = None if ret is None else (ret > 0 if r["direction"] == "bull" else ret < 0 if r["direction"] == "bear" else None)
        out.append({**r, "fired_at": ms_to_iso(r["fired_ts"]),
                    "since_ret": round(ret, 4) if ret is not None else None, "on_track": on_track})
    tracked = [o for o in out if o["on_track"] is not None]
    hit = sum(1 for o in tracked if o["on_track"])
    return {"count": len(out), "on_track_rate": round(hit / len(tracked), 3) if tracked else None, "alerts": out}


@app.get("/alert-calibration/{symbol}")
def alert_calibration(
    symbol: str,
    timeframe: str = Query(default="4h"),
    horizon: int = Query(default=12, ge=1, le=200),
) -> dict:
    """Per-alert-type forward hit-rate/lift for a symbol (does each setup work?)."""
    rows = _load_candles(symbol, timeframe)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no {timeframe} data for {symbol}")
    rep = calibrate_alerts(rows, _load_funding(symbol), horizon=horizon)
    if rep is None:
        raise HTTPException(status_code=422, detail="not enough history to calibrate")
    return {"symbol": symbol, "timeframe": timeframe, **rep}


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

    onchain = _load_onchain(symbol)
    note = generate_commentary(
        rows, timeframe, micro=micro, sentiment=sentiment_bundle, funding_rows=funding_rows,
        positioning=positioning, derivatives=derivatives, htf=htf, outlook_calibration=outlook_cal,
        onchain=onchain,
        vol_iv=_cached(("iv", symbol, timeframe), 600, lambda: implied_vol_context(symbol, rows, timeframe)),
    )
    # focused per-metric breakdown (each signal read on its own)
    reads = metric_reads(
        rows, timeframe, micro=micro, sentiment=sentiment_bundle, funding_rows=funding_rows,
        positioning=positioning, derivatives=derivatives, htf=htf, onchain=onchain, horizon=horizon,
    )
    return {"symbol": symbol, "timeframe": timeframe, "as_of": ms_to_iso(rows[-1]["ts"]),
            "metric_reads": reads, **note}


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
