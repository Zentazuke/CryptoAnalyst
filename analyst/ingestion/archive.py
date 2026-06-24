"""Raw-payload archival.

We persist the untouched source response to disk before (and independently of)
parsing. If a parser bug is ever discovered, the raw archive lets us recompute
from ground truth rather than from already-transformed data.
"""
from __future__ import annotations

import json
from pathlib import Path

from analyst.utils import now_ms


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
    return path
