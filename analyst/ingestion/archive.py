"""Raw-payload archival.

We persist the untouched source response to disk before (and independently of)
parsing. If a parser bug is ever discovered, the raw archive lets us recompute
from ground truth rather than from already-transformed data.

RETENTION (added 2026-10-13): the archive had no retention and grew to 23 GB in
~3 months of 24/7 scheduler running (microstructure every 2 min x 7 coins),
filling the server disk and halting all DB writes. Files older than
ANALYST_RAW_RETENTION_DAYS (default 7) are now pruned automatically, at most
once per hour, from inside the writer — no extra cron to forget. Parsed data
lives in DuckDB and is unaffected; the raw archive is a short replay buffer.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from analyst.utils import now_ms

RETENTION_DAYS = float(os.environ.get("ANALYST_RAW_RETENTION_DAYS", "7"))
_PRUNE_EVERY_S = 3600
_last_prune: dict[str, float] = {}


def prune_raw(raw_dir: Path, retention_days: float = RETENTION_DAYS) -> int:
    """Delete archived payloads older than ``retention_days``. Returns count.
    retention_days <= 0 disables pruning (keep forever)."""
    if retention_days <= 0 or not raw_dir.exists():
        return 0
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for p in raw_dir.glob("*.json"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except OSError:  # raced with another writer/pruner — harmless
            pass
    return removed


def archive_raw(
    raw: dict,
    source: str,
    symbol: str,
    timeframe: str,
    raw_dir: Path,
) -> Path:
    """Write ``raw`` to ``raw_dir`` and return the file path.

    Filenames embed source, symbol, timeframe, and the archival timestamp so
    the archive is self-describing and naturally ordered.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe_source = source.replace("/", "-").replace(".", "-")
    fname = f"{safe_source}__{symbol}__{timeframe}__{now_ms()}.json"
    path = raw_dir / fname
    path.write_text(json.dumps(raw, separators=(",", ":")), encoding="utf-8")

    key = str(raw_dir)
    now = time.time()
    if now - _last_prune.get(key, 0.0) >= _PRUNE_EVERY_S:
        _last_prune[key] = now
        try:
            prune_raw(raw_dir)
        except Exception:  # noqa: BLE001 — pruning must never break ingestion
            pass
    return path
