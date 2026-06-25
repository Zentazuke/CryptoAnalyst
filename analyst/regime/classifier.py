"""Rule-based regime classifier (v1): transparent and causal.

Decision order (first match wins), per bar:
  1. flash_risk     — a large one-bar move (>= flash_ret_atr ATRs) on a volume
                      spike: a shock, dangerous for passive strategies.
  2. breakout       — close escapes the prior Donchian channel while Bollinger
                      bandwidth is expanding: a range break in progress.
  3. trend_up/down  — ADX >= adx_trend with agreeing DI and EMA slope.
  4. low_vol_drift  — ATR% in the low tail of its recent distribution and ADX
                      below adx_range: quiet drift (fee-drag risk for grids).
  5. range          — the default: non-trending oscillation (grid-friendly).

Every result carries a confidence in [0,1] and the contributing feature values
plus human-readable reasons, so a call can always be audited.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from pydantic import BaseModel

from analyst.regime.features import REGIME_DEFAULTS, compute_regime_features

RANGE = "range"
TREND_UP = "trend_up"
TREND_DOWN = "trend_down"
BREAKOUT = "breakout"
FLASH_RISK = "flash_risk"
LOW_VOL_DRIFT = "low_vol_drift"
UNKNOWN = "unknown"
LABELS = [RANGE, TREND_UP, TREND_DOWN, BREAKOUT, FLASH_RISK, LOW_VOL_DRIFT, UNKNOWN]

# thresholds (merged over REGIME_DEFAULTS)
THRESHOLDS: dict[str, float] = {
    "adx_trend": 25.0,
    "adx_range": 20.0,
    "adx_strong": 40.0,      # ADX mapped to full trend confidence
    "flash_ret_atr": 3.0,    # one-bar move (in ATRs) for a shock
    "vol_spike_z": 2.0,      # volume z-score for a shock
    "low_vol_rank": 0.20,    # ATR% percentile-rank tail for low-vol drift
}


class RegimeResult(BaseModel):
    ts: int | None = None
    label: str
    confidence: float
    features: dict[str, float | None]
    reasons: list[str]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _f(v: float) -> float | None:
    return float(v) if v is not None and np.isfinite(v) else None


def _classify_one(feat: dict[str, float], thr: dict[str, float]) -> tuple[str, float, list[str]]:
    adx = feat["adx"]
    plus_di = feat["plus_di"]
    minus_di = feat["minus_di"]
    ema_slope = feat["ema_slope"]
    bandwidth_chg = feat["bandwidth_chg"]
    atr_pct = feat["atr_pct"]
    atr_pct_rank = feat["atr_pct_rank"]
    donchian_hi = feat["donchian_hi"]
    donchian_lo = feat["donchian_lo"]
    ret_atr = feat["ret_atr"]
    vol_z = feat["vol_z"]
    close = feat["close"]

    # Require the core trend/vol features; otherwise we cannot judge.
    if any(not np.isfinite(x) for x in (adx, atr_pct, ret_atr)):
        return UNKNOWN, 0.0, ["insufficient history"]

    # 1) flash_risk -------------------------------------------------------
    # A large one-bar move (in ATRs) is itself a shock; a volume spike, when
    # available, raises confidence but does not gate the call.
    if abs(ret_atr) >= thr["flash_ret_atr"]:
        conf = _clamp01(abs(ret_atr) / (2.0 * thr["flash_ret_atr"]))
        reasons = [f"1-bar move {ret_atr:+.1f} ATR (>= {thr['flash_ret_atr']})"]
        if np.isfinite(vol_z) and vol_z >= thr["vol_spike_z"]:
            conf = _clamp01(conf + 0.15)
            reasons.append(f"volume z {vol_z:+.1f} (>= {thr['vol_spike_z']})")
        return FLASH_RISK, conf, reasons

    # 2) trend ------------------------------------------------------------
    # Checked before breakout: an established trend that keeps making new highs
    # or lows is a trend, not a fresh range break.
    if adx >= thr["adx_trend"]:
        conf = _clamp01((adx - thr["adx_range"]) / (thr["adx_strong"] - thr["adx_range"]))
        up = plus_di > minus_di and (not np.isfinite(ema_slope) or ema_slope >= 0)
        down = minus_di > plus_di and (not np.isfinite(ema_slope) or ema_slope <= 0)
        if up:
            return TREND_UP, conf, [
                f"ADX {adx:.1f} >= {thr['adx_trend']}",
                f"+DI {plus_di:.1f} > -DI {minus_di:.1f}",
                f"EMA slope {ema_slope:+.3f}" if np.isfinite(ema_slope) else "EMA slope n/a",
            ]
        if down:
            return TREND_DOWN, conf, [
                f"ADX {adx:.1f} >= {thr['adx_trend']}",
                f"-DI {minus_di:.1f} > +DI {plus_di:.1f}",
                f"EMA slope {ema_slope:+.3f}" if np.isfinite(ema_slope) else "EMA slope n/a",
            ]
        # strong ADX but DI/slope disagree -> chop; fall through

    # 3) breakout ---------------------------------------------------------
    # Only reached when not already trending (ADX < adx_trend): price escaping
    # the prior range while volatility expands.
    expanding = np.isfinite(bandwidth_chg) and bandwidth_chg > 0
    if np.isfinite(donchian_hi) and close > donchian_hi and expanding:
        conf = _clamp01((close - donchian_hi) / (atr_pct * close + 1e-9))
        return BREAKOUT, _clamp01(0.4 + 0.6 * conf), [
            "close above prior Donchian high",
            "Bollinger bandwidth expanding",
        ]
    if np.isfinite(donchian_lo) and close < donchian_lo and expanding:
        conf = _clamp01((donchian_lo - close) / (atr_pct * close + 1e-9))
        return BREAKOUT, _clamp01(0.4 + 0.6 * conf), [
            "close below prior Donchian low",
            "Bollinger bandwidth expanding",
        ]

    # 4) low-vol drift ----------------------------------------------------
    if (
        np.isfinite(atr_pct_rank)
        and atr_pct_rank <= thr["low_vol_rank"]
        and adx < thr["adx_range"]
    ):
        conf = _clamp01((thr["low_vol_rank"] - atr_pct_rank) / thr["low_vol_rank"])
        return LOW_VOL_DRIFT, conf, [
            f"ATR% percentile {atr_pct_rank:.2f} <= {thr['low_vol_rank']}",
            f"ADX {adx:.1f} < {thr['adx_range']}",
        ]

    # 5) range (default) --------------------------------------------------
    conf = _clamp01((thr["adx_range"] - min(adx, thr["adx_range"])) / thr["adx_range"])
    return RANGE, conf, [f"ADX {adx:.1f} < {thr['adx_trend']} (non-trending)"]


def classify_series(
    candles: list[Any], params: dict | None = None
) -> list[RegimeResult]:
    """Classify every bar. Causal: bar ``i`` uses only data up to ``i``."""
    p = {**REGIME_DEFAULTS, **THRESHOLDS, **(params or {})}
    thr = {k: p[k] for k in THRESHOLDS}
    feats = compute_regime_features(candles, p)
    names = list(feats.keys())
    n = len(candles)

    results: list[RegimeResult] = []
    for i in range(n):
        row = {name: feats[name][i] for name in names}
        label, conf, reasons = _classify_one(row, thr)
        ts = candles[i]["ts"] if isinstance(candles[i], dict) else getattr(candles[i], "ts", None)
        results.append(
            RegimeResult(
                ts=ts,
                label=label,
                confidence=round(conf, 4),
                features={k: _f(row[k]) for k in names if k != "close"},
                reasons=reasons,
            )
        )
    return results


def classify_latest(candles: list[Any], params: dict | None = None) -> RegimeResult:
    if not candles:
        return RegimeResult(label=UNKNOWN, confidence=0.0, features={}, reasons=["no data"])
    return classify_series(candles, params)[-1]
