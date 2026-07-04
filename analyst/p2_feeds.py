"""P2 Tier-1 data feeds — options surface, derivatives crowd, stablecoin supply.

Each fetcher returns a FLAT dict of numeric metrics (or None if unavailable) and
is recorded into MetricHistory by the scheduler, starting the calibration clock.
Per the upgrade plan these are DECORATION until the P1.2 harness scores them on
accrued history — nothing here feeds a decision yet.

Sources (all keyless/public):
  * Deribit  `get_book_summary_by_currency` — whole options board in one call:
    per-expiry ATM IV, term-structure slope, and a ±10%-moneyness risk-reversal
    proxy for skew. (A true 25Δ RR needs greeks per instrument = N calls; the
    fixed-moneyness proxy is one call and, for calibration, CONSISTENCY over
    time matters more than convention.)
  * Binance USDT-M futures `futures/data/*` — taker buy/sell volume ratio, top-
    trader account long/short ratio, open interest + its 1h change (the crowd).
  * DefiLlama `stablecoins.llama.fi` — USDT/USDC/total circulating supply (the
    on-chain dry-powder gauge the Trading Bot already found useful as context).

Fetchers take an injectable `get_json` so tests run on canned payloads with no
network. The default helper uses httpx (house standard).
"""
from __future__ import annotations

import math
import time
from typing import Any, Callable

MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
          "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

DERIBIT_BASE = "https://www.deribit.com/api/v2/public"
BINANCE_FUT = "https://fapi.binance.com/futures/data"
LLAMA_URL = "https://stablecoins.llama.fi/stablecoins?includePrices=false"


def default_get_json(url: str, timeout: float = 15.0) -> Any:
    import httpx
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _parse_expiry_ms(instrument: str) -> int | None:
    """'BTC-26SEP25-100000-C' -> expiry as UTC ms (08:00 UTC settlement)."""
    try:
        part = instrument.split("-")[1]
        day = int(part[:2] if part[:2].isdigit() else part[:1])
        rest = part[2:] if part[:2].isdigit() else part[1:]
        mon = MONTHS[rest[:3].upper()]
        year = 2000 + int(rest[3:])
        from datetime import datetime, timezone
        return int(datetime(year, mon, day, 8, tzinfo=timezone.utc).timestamp() * 1000)
    except Exception:  # noqa: BLE001 — unexpected name shape -> skip instrument
        return None


def options_surface(currency: str = "BTC",
                    get_json: Callable = default_get_json,
                    now_ms: int | None = None) -> dict[str, float] | None:
    """ATM IV near/far, term slope, and a ±10%-moneyness skew proxy."""
    cur = currency.upper()
    try:
        rows = get_json(f"{DERIBIT_BASE}/get_book_summary_by_currency"
                        f"?currency={cur}&kind=option").get("result") or []
    except Exception:  # noqa: BLE001
        return None
    now = now_ms or int(time.time() * 1000)

    by_exp: dict[int, list[dict]] = {}
    under = None
    for r in rows:
        iv = r.get("mark_iv")
        u = r.get("underlying_price")
        exp = _parse_expiry_ms(r.get("instrument_name", ""))
        if not iv or not u or not exp or exp <= now + 7 * 86_400_000:
            continue  # skip expiring-this-week noise and dead quotes
        try:
            parts = r["instrument_name"].split("-")
            strike = float(parts[2])
            opt_type = parts[3]
        except Exception:  # noqa: BLE001
            continue
        under = float(u)
        by_exp.setdefault(exp, []).append(
            {"strike": strike, "iv": float(iv), "type": opt_type})
    if not by_exp or not under:
        return None

    def _closest_exp(target_days: float, exclude: int | None = None) -> int | None:
        cands = [e for e in by_exp if e != exclude]
        if not cands:
            return None
        return min(cands, key=lambda e: abs((e - now) / 86_400_000 - target_days))

    def _atm_iv(exp: int) -> float | None:
        chain = by_exp[exp]
        best = min(chain, key=lambda c: abs(c["strike"] - under))
        return best["iv"]

    def _iv_at(exp: int, moneyness: float, opt_type: str) -> float | None:
        chain = [c for c in by_exp[exp] if c["type"] == opt_type]
        if not chain:
            return None
        tgt = under * moneyness
        best = min(chain, key=lambda c: abs(c["strike"] - tgt))
        if abs(best["strike"] - tgt) / under > 0.10:
            return None  # nothest strike is too far to call it that moneyness
        return best["iv"]

    near = _closest_exp(30.0)
    far = _closest_exp(90.0, exclude=near)
    if near is None:
        return None
    out: dict[str, float] = {"n_instruments": float(sum(len(v) for v in by_exp.values()))}
    atm_near = _atm_iv(near)
    if atm_near is None or not math.isfinite(atm_near):
        return None
    out["atm_iv_near"] = atm_near
    out["days_near"] = round((near - now) / 86_400_000, 1)
    if far is not None:
        atm_far = _atm_iv(far)
        if atm_far is not None:
            out["atm_iv_far"] = atm_far
            out["term_slope"] = round(atm_far - atm_near, 3)
            out["days_far"] = round((far - now) / 86_400_000, 1)
    put = _iv_at(near, 0.90, "P")
    call = _iv_at(near, 1.10, "C")
    if put is not None and call is not None:
        out["rr_10pct"] = round(put - call, 3)   # >0 = downside fear premium
    return out


def derivs_crowd(symbol: str = "BTC_USDT",
                 get_json: Callable = default_get_json) -> dict[str, float] | None:
    """Crowd/positioning snapshot from Binance USDT-M public futures data."""
    pair = symbol.replace("_", "").replace("/", "")
    out: dict[str, float] = {}
    try:
        t = get_json(f"{BINANCE_FUT}/takerlongshortRatio?symbol={pair}&period=1h&limit=1")
        if t:
            out["taker_buy_sell_ratio"] = float(t[-1]["buySellRatio"])
    except Exception:  # noqa: BLE001
        pass
    try:
        a = get_json(f"{BINANCE_FUT}/topLongShortAccountRatio?symbol={pair}&period=1h&limit=1")
        if a:
            out["top_ls_account_ratio"] = float(a[-1]["longShortRatio"])
    except Exception:  # noqa: BLE001
        pass
    try:
        oi = get_json(f"{BINANCE_FUT}/openInterestHist?symbol={pair}&period=1h&limit=2")
        if oi:
            cur = float(oi[-1]["sumOpenInterestValue"])
            out["oi_usd"] = cur
            if len(oi) > 1:
                prev = float(oi[-2]["sumOpenInterestValue"])
                if prev > 0:
                    out["oi_change_1h_pct"] = round((cur / prev - 1) * 100, 4)
    except Exception:  # noqa: BLE001
        pass
    return out or None


def stable_supply(get_json: Callable = default_get_json) -> dict[str, float] | None:
    """USDT/USDC/total circulating (peggedUSD) from DefiLlama — dry powder."""
    try:
        data = get_json(LLAMA_URL)
    except Exception:  # noqa: BLE001
        return None
    assets = data.get("peggedAssets") or []
    out: dict[str, float] = {}
    total = 0.0
    for a in assets:
        circ = ((a.get("circulating") or {}).get("peggedUSD"))
        if circ is None:
            continue
        total += float(circ)
        sym = (a.get("symbol") or "").upper()
        if sym in ("USDT", "USDC"):
            out[f"{sym.lower()}_circulating"] = float(circ)
    if not out:
        return None
    out["total_stable_circulating"] = total
    if "usdt_circulating" in out and "usdc_circulating" in out:
        out["majors_circulating"] = out["usdt_circulating"] + out["usdc_circulating"]
    return out
