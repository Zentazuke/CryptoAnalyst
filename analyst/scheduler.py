"""In-process background collector.

Runs inside the API process as a daemon thread so the service is self-feeding:
it keeps recent candles fresh, accrues microstructure and funding history, and
journals fired alerts over time (so the trust signals actually mature). It rides
a sibling cursor off the API's read-write connection — one DuckDB instance, no
second handle — and every task is isolated in try/except so a transient fetch
error can never take the API down.

Enabled only when ANALYST_SCHEDULER=1 (see config); otherwise the API stays a
plain read-only reader, which is what tests and ad-hoc runs use.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from analyst.alerts import detect_alerts
from analyst.config import (
    DEPTH_BAND_BPS, SCHEDULER_INTERVALS, SCHEDULER_SYMBOLS, SCHEDULER_TIMEFRAMES,
)
from analyst.ingest import ingest_symbol
from analyst.ingestion import make_source
from analyst.microstructure import collect_microstructure
from analyst.scanner import scan_symbols
from analyst.storage import Store
from analyst.storage.journal import AlertJournal

log = logging.getLogger("analyst.scheduler")

TICK_SECONDS = 15  # how often we wake to check which tasks are due


class Task:
    def __init__(self, name: str, interval_s: int, fn: Callable[[], None]):
        self.name = name
        self.interval_s = interval_s
        self.fn = fn
        self.last_run = 0.0
        self.runs = 0
        self.errors = 0

    def due(self, now: float) -> bool:
        return now - self.last_run >= self.interval_s


class Scheduler:
    """Daemon thread that runs collection tasks on independent cadences."""

    def __init__(self, conn, symbols=None, timeframes=None, intervals=None):
        # share the API's RW connection via a sibling cursor (thread-safe)
        self.store = Store(conn=conn.cursor())
        self.symbols = symbols or SCHEDULER_SYMBOLS
        self.timeframes = timeframes or SCHEDULER_TIMEFRAMES
        iv = {**SCHEDULER_INTERVALS, **(intervals or {})}
        self._source = None
        self._journal: AlertJournal | None = None
        self._vrp_journal = None
        self._metrics = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.tasks = [
            Task("candles", iv["candles"], self._candles),
            Task("microstructure", iv["microstructure"], self._microstructure),
            Task("funding", iv["funding"], self._funding),
            Task("alert_journal", iv["alert_journal"], self._alert_journal),
            Task("vrp_journal", iv.get("vrp_journal", 21600), self._vrp_journal_task),
            Task("metric_history", iv.get("metric_history", 1800), self._metric_history),
            Task("p2_feeds", iv.get("p2_feeds", 3600), self._p2_feeds),
        ]

    # ---- lifecycle --------------------------------------------------------
    def start(self) -> None:
        self._source = make_source()
        self._thread = threading.Thread(target=self._loop, name="analyst-scheduler", daemon=True)
        self._thread.start()
        log.info("scheduler started: symbols=%s timeframes=%s", self.symbols, self.timeframes)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        if self._source and hasattr(self._source, "close"):
            try:
                self._source.close()
            except Exception:  # pragma: no cover
                pass

    def status(self) -> dict:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "symbols": self.symbols,
            "timeframes": self.timeframes,
            "tasks": [
                {"name": t.name, "interval_s": t.interval_s, "runs": t.runs,
                 "errors": t.errors, "last_run": t.last_run}
                for t in self.tasks
            ],
        }

    # ---- loop -------------------------------------------------------------
    def _loop(self) -> None:
        # stagger the first run so we don't fetch everything at once on boot
        time.sleep(2)
        while not self._stop.is_set():
            now = time.time()
            for t in self.tasks:
                if self._stop.is_set():
                    break
                if t.due(now):
                    try:
                        t.fn()
                        t.runs += 1
                    except Exception as e:  # never let a task kill the thread
                        t.errors += 1
                        log.warning("scheduler task %s failed: %s", t.name, e)
                    finally:
                        t.last_run = time.time()
            self._stop.wait(TICK_SECONDS)

    # ---- tasks ------------------------------------------------------------
    # Each task isolates per-symbol failures: a coin with no perp (no funding)
    # or a transient fetch error must not abort collection for the others.
    def _candles(self) -> None:
        for sym in self.symbols:
            for tf in self.timeframes:
                try:
                    ingest_symbol(sym, tf, 300, self.store, self._source)
                except Exception as e:
                    log.warning("candles %s %s failed: %s", sym, tf, e)

    def _microstructure(self) -> None:
        for sym in self.symbols:
            try:
                collect_microstructure(sym, self._source, self.store, band_bps=DEPTH_BAND_BPS)
            except Exception as e:
                log.warning("microstructure %s failed: %s", sym, e)

    def _funding(self) -> None:
        for sym in self.symbols:
            perp = self._source.perp_for(sym) if hasattr(self._source, "perp_for") else None
            if not perp or not hasattr(self._source, "fetch_funding_history"):
                continue
            try:
                rows, _ = self._source.fetch_funding_history(perp, total=1000)
                if rows:
                    self.store.upsert_funding(sym, rows, self._source.name)
            except Exception as e:
                # common for spot-only coins (no perp) — log quietly and move on
                log.info("funding %s unavailable: %s", sym, e)

    def _alert_journal(self) -> None:
        if self._journal is None:
            self._journal = AlertJournal()
        tf = self.timeframes[0] if self.timeframes else "4h"
        result = scan_symbols(self._source, self.symbols, timeframe=tf, count=300)
        rows = result.get("rows", [])
        for r in rows:  # alert detection expects a price field
            r.setdefault("price", r.get("price"))
        alerts = detect_alerts(rows)
        if alerts:
            self._journal.record(alerts, tf)

    def _metric_history(self) -> None:
        """P1.1: persist sentiment + on-chain snapshots so those layers accrue
        the history calibration needs. Engine offline / no coverage is normal —
        skip quietly and try again next cycle."""
        from analyst.ingestion.sentiment import SentimentClient
        from analyst.onchain import onchain_snapshot
        from analyst.storage.history import MetricHistory, flatten_numeric
        if self._metrics is None:
            self._metrics = MetricHistory()
        with SentimentClient() as sc:
            for sym in self.symbols:
                try:
                    bundle = sc.bundle(sym)
                    if bundle:
                        self._metrics.record("sentiment", sym, flatten_numeric(bundle),
                                             "sentiment-engine", min_gap_s=900)
                except Exception as e:
                    log.info("sentiment history %s unavailable: %s", sym, e)
        for sym in self.symbols:
            try:
                snap = onchain_snapshot(sym)
                if snap:
                    self._metrics.record("onchain", sym, flatten_numeric(snap),
                                         "coinmetrics", min_gap_s=6 * 3600)
            except Exception as e:
                log.info("onchain history %s unavailable: %s", sym, e)

    def _p2_feeds(self) -> None:
        """P2 Tier-1: persist options surface (BTC/ETH), derivatives crowd (all
        scheduled symbols), and global stablecoin supply into MetricHistory —
        starting their calibration clocks. All parts fail independently."""
        from analyst.p2_feeds import derivs_crowd, options_surface, stable_supply
        from analyst.storage.history import MetricHistory
        if self._metrics is None:
            self._metrics = MetricHistory()
        for cur in ("BTC", "ETH"):
            try:
                surf = options_surface(cur)
                if surf:
                    self._metrics.record("options", f"{cur}_USDT", surf,
                                         "deribit", min_gap_s=1800)
            except Exception as e:  # noqa: BLE001
                log.info("options surface %s unavailable: %s", cur, e)
        for sym in self.symbols:
            try:
                crowd = derivs_crowd(sym)
                if crowd:
                    self._metrics.record("derivatives", sym, crowd,
                                         "binance-futures", min_gap_s=1800)
            except Exception as e:  # noqa: BLE001
                log.info("derivs crowd %s unavailable: %s", sym, e)
        try:
            stab = stable_supply()
            if stab:
                self._metrics.record("stableflow", "GLOBAL", stab,
                                     "defillama", min_gap_s=6 * 3600)
        except Exception as e:  # noqa: BLE001
            log.info("stable supply unavailable: %s", e)

    def _vrp_journal_task(self) -> None:
        """Record the daily VRP read for BTC/ETH so it forward-validates live."""
        from analyst.ingestion.deribit import DeribitSource
        from analyst.storage.vrp_journal import VrpJournal
        from analyst.vrp_live import vrp_read
        if self._vrp_journal is None:
            self._vrp_journal = VrpJournal()
        src = DeribitSource()
        try:
            for sym in ("BTC_USDT", "ETH_USDT"):
                rows = self.store.get_candles(sym, "1D")
                if not rows:
                    continue
                read = vrp_read(sym.split("_")[0], rows, source=src)
                if read:
                    self._vrp_journal.record(read)
        finally:
            src.close()
