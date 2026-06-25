"""Read-only connectivity check for the Binance SPOT testnet credentials.

Loads BINANCE_TESTNET_API_KEY / _SECRET from the project's .env, then makes a
single *signed, read-only* account query (no orders) to confirm the key is
valid and trading-enabled. Never prints the secret.

    python scripts/check_binance_testnet.py
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
from pathlib import Path

import httpx

BASE = "https://testnet.binance.vision"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    _load_env(PROJECT_ROOT / ".env")
    key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
    sec = os.environ.get("BINANCE_TESTNET_API_SECRET", "")
    if not key or not sec:
        print("No BINANCE_TESTNET_API_KEY / _SECRET found in .env")
        return 2

    try:
        server_time = httpx.get(f"{BASE}/api/v3/time", timeout=15).json()["serverTime"]
        query = f"timestamp={server_time}&recvWindow=5000"
        sig = hmac.new(sec.encode(), query.encode(), hashlib.sha256).hexdigest()
        resp = httpx.get(
            f"{BASE}/api/v3/account?{query}&signature={sig}",
            headers={"X-MBX-APIKEY": key},
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"request failed: {type(exc).__name__}: {exc}")
        return 1

    if resp.status_code != 200:
        print(f"AUTH FAILED  HTTP {resp.status_code}: {resp.text[:200]}")
        return 1

    data = resp.json()
    funded = sum(
        1 for b in data.get("balances", []) if float(b["free"]) + float(b["locked"]) > 0
    )
    print("AUTH OK")
    print(f"  accountType : {data.get('accountType')}")
    print(f"  canTrade    : {data.get('canTrade')}")
    print(f"  funded assets: {funded}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
