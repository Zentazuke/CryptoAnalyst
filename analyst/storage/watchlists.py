"""User watchlists (P3.1) — named symbol lists ('Majors', 'High funding', ...).

Own DuckDB file, same pattern as AlertJournal: the API's market DB stays
read-only. Thread-safe; symbols are stored in the analyst's BASE_QUOTE form.
"""
from __future__ import annotations

import threading

import duckdb

from analyst.config import DATA_DIR
from analyst.utils import now_ms

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlists (
    name     VARCHAR,
    symbol   VARCHAR,
    added_ts BIGINT
);
"""


def _norm(symbol: str) -> str:
    return symbol.strip().upper().replace("/", "_").replace("-", "_")


class Watchlists:
    def __init__(self, path: str | None = None) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = str(path or (DATA_DIR / "watchlists.duckdb"))
        self._lock = threading.Lock()
        self.conn = duckdb.connect(self.path)
        self.conn.execute(_SCHEMA)

    def add(self, name: str, symbols: list[str]) -> int:
        """Add symbols to a list (created implicitly). Duplicates are skipped."""
        name = name.strip()
        if not name:
            return 0
        added = 0
        with self._lock:
            existing = {r[0] for r in self.conn.execute(
                "SELECT symbol FROM watchlists WHERE name=?", [name]).fetchall()}
            for s in symbols:
                sym = _norm(s)
                if not sym or sym in existing:
                    continue
                self.conn.execute("INSERT INTO watchlists VALUES (?, ?, ?)",
                                  [name, sym, now_ms()])
                existing.add(sym)
                added += 1
        return added

    def remove(self, name: str, symbol: str | None = None) -> int:
        """Remove one symbol, or the whole list when symbol is None."""
        with self._lock:
            if symbol is None:
                n = self.conn.execute("SELECT COUNT(*) FROM watchlists WHERE name=?",
                                      [name]).fetchone()[0]
                self.conn.execute("DELETE FROM watchlists WHERE name=?", [name])
                return int(n)
            n = self.conn.execute(
                "SELECT COUNT(*) FROM watchlists WHERE name=? AND symbol=?",
                [name, _norm(symbol)]).fetchone()[0]
            self.conn.execute("DELETE FROM watchlists WHERE name=? AND symbol=?",
                              [name, _norm(symbol)])
            return int(n)

    def lists(self) -> dict[str, list[str]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT name, symbol FROM watchlists ORDER BY name, added_ts").fetchall()
        out: dict[str, list[str]] = {}
        for name, sym in rows:
            out.setdefault(name, []).append(sym)
        return out

    def get(self, name: str) -> list[str]:
        with self._lock:
            return [r[0] for r in self.conn.execute(
                "SELECT symbol FROM watchlists WHERE name=? ORDER BY added_ts",
                [name]).fetchall()]
