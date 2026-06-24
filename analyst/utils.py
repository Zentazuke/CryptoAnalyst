"""Small shared helpers."""
from __future__ import annotations

import time


def now_ms() -> int:
    """Current wall-clock time in milliseconds since the Unix epoch."""
    return int(time.time() * 1000)


def ms_to_iso(ts_ms: int) -> str:
    """Render a ms-epoch timestamp as a UTC ISO-8601 string (for display/logs)."""
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
