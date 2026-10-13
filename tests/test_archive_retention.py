"""Raw archive retention: old files pruned, fresh kept, disabled at <=0."""
from __future__ import annotations

import os
import time

from analyst.ingestion import archive


def _old(path, days):
    t = time.time() - days * 86400
    os.utime(path, (t, t))


def test_prune_removes_only_old(tmp_path):
    fresh = archive.archive_raw({"a": 1}, "src", "BTC_USDT", "1h", tmp_path)
    old = tmp_path / "src__BTC_USDT__1h__1.json"
    old.write_text("{}")
    _old(old, 10)
    assert archive.prune_raw(tmp_path, retention_days=7) == 1
    assert fresh.exists() and not old.exists()


def test_prune_disabled(tmp_path):
    old = tmp_path / "x.json"
    old.write_text("{}")
    _old(old, 100)
    assert archive.prune_raw(tmp_path, retention_days=0) == 0
    assert old.exists()


def test_writer_prunes_automatically(tmp_path, monkeypatch):
    old = tmp_path / "src__ETH_USDT__1h__1.json"
    old.write_text("{}")
    _old(old, 30)
    archive._last_prune.clear()
    archive.archive_raw({"b": 2}, "src", "ETH_USDT", "1h", tmp_path)
    assert not old.exists()
