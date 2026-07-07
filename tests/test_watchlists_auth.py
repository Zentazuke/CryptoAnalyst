"""Watchlists store roundtrip + bearer-token auth middleware."""
from __future__ import annotations

from analyst.storage.watchlists import Watchlists


def test_watchlist_roundtrip(tmp_path):
    w = Watchlists(path=str(tmp_path / "wl.duckdb"))
    assert w.add("Majors", ["BTC/USDT", "eth_usdt", "BTC_USDT"]) == 2  # dupe skipped
    assert w.get("Majors") == ["BTC_USDT", "ETH_USDT"]
    assert w.add("Majors", ["SOL_USDT"]) == 1
    assert w.remove("Majors", "ETH/USDT") == 1
    assert w.get("Majors") == ["BTC_USDT", "SOL_USDT"]
    w.add("AI coins", ["FET_USDT"])
    assert set(w.lists()) == {"Majors", "AI coins"}
    assert w.remove("Majors") == 2            # whole list
    assert w.get("Majors") == []
    assert w.add("", ["BTC_USDT"]) == 0       # nameless -> refused


def test_bearer_auth_toggle(monkeypatch):
    from fastapi.testclient import TestClient

    from analyst.api.app import app
    client = TestClient(app)                   # no context manager -> no lifespan

    # token unset -> open
    monkeypatch.delenv("ANALYST_API_TOKEN", raising=False)
    assert client.get("/scheduler").status_code == 200

    # token set -> guarded (except /health)
    monkeypatch.setenv("ANALYST_API_TOKEN", "s3cret")
    assert client.get("/scheduler").status_code == 401
    assert client.get("/scheduler",
                      headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/scheduler",
                      headers={"Authorization": "Bearer s3cret"}).status_code == 200
    assert client.get("/health").status_code != 401   # exempt (503 without store is fine)
