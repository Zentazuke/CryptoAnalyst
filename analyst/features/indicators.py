"""Causal technical indicators.

Every function takes 1-D numeric input and returns a float ``np.ndarray`` of the
same length, with ``np.nan`` during the warmup period. All are **causal**: the
value at index ``i`` depends only on inputs at indices ``<= i`` (verified by the
no-look-ahead test suite).

Conventions (chosen to match the TA-Lib reference):
  * EMA is seeded with the SMA of the first ``n`` samples (not the first sample).
  * RSI / ATR / ADX use Wilder's smoothing (RMA), also SMA-seeded.
  * Bollinger and rolling std use population std (ddof = 0).
"""
from __future__ import annotations

import numpy as np

__all__ = [
    "sma", "ema", "rolling_std", "bollinger", "rsi",
    "true_range", "atr", "adx", "vwap", "realized_vol",
]


def _as_float(x) -> np.ndarray:
    return np.asarray(x, dtype=float)


def sma(values, n: int) -> np.ndarray:
    """Simple moving average. First valid value at index ``n-1``."""
    v = _as_float(values)
    out = np.full(v.shape, np.nan)
    if len(v) >= n >= 1:
        csum = np.cumsum(np.insert(v, 0, 0.0))
        out[n - 1:] = (csum[n:] - csum[:-n]) / n
    return out


def _ema_seeded(values: np.ndarray, n: int, first_valid: int = 0) -> np.ndarray:
    """EMA seeded with the SMA of ``n`` samples starting at ``first_valid``."""
    v = _as_float(values)
    out = np.full(v.shape, np.nan)
    seed_end = first_valid + n
    if len(v) < seed_end or n < 1:
        return out
    alpha = 2.0 / (n + 1.0)
    out[seed_end - 1] = np.mean(v[first_valid:seed_end])
    for i in range(seed_end, len(v)):
        out[i] = alpha * v[i] + (1.0 - alpha) * out[i - 1]
    return out


def ema(values, n: int) -> np.ndarray:
    """Exponential moving average (SMA-seeded). First valid at index ``n-1``."""
    return _ema_seeded(_as_float(values), n, first_valid=0)


def rolling_std(values, n: int) -> np.ndarray:
    """Rolling population standard deviation (ddof = 0)."""
    v = _as_float(values)
    out = np.full(v.shape, np.nan)
    for i in range(n - 1, len(v)):
        out[i] = v[i - n + 1:i + 1].std(ddof=0)
    return out


def bollinger(values, n: int = 20, k: float = 2.0):
    """Bollinger bands. Returns (middle, upper, lower, bandwidth)."""
    mid = sma(values, n)
    sd = rolling_std(values, n)
    upper = mid + k * sd
    lower = mid - k * sd
    with np.errstate(divide="ignore", invalid="ignore"):
        bandwidth = (upper - lower) / mid
    return mid, upper, lower, bandwidth


def _wilder_rma(values: np.ndarray, n: int) -> np.ndarray:
    """Wilder's smoothing (RMA). Robust to leading NaNs in ``values``.

    Seeds with the mean of the first ``n`` valid (non-NaN) samples and then
    applies ``rma_i = (rma_{i-1}*(n-1) + x_i)/n``.
    """
    v = _as_float(values)
    size = len(v)
    out = np.full(size, np.nan)
    valid = np.where(~np.isnan(v))[0]
    if len(valid) < n or n < 1:
        return out
    f = int(valid[0])
    if f + n > size:
        return out
    out[f + n - 1] = np.mean(v[f:f + n])
    for i in range(f + n, size):
        out[i] = (out[i - 1] * (n - 1) + v[i]) / n
    return out


def rsi(values, n: int = 14) -> np.ndarray:
    """Wilder's RSI. First valid value at index ``n``.

    A flat window (no gains and no losses) is reported as the neutral 50.
    """
    v = _as_float(values)
    size = len(v)
    out = np.full(size, np.nan)
    if size < 2:
        return out
    delta = np.diff(v)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = _wilder_rma(gain, n)
    avg_loss = _wilder_rma(loss, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.divide(avg_gain, avg_loss)
        rsi_d = 100.0 - 100.0 / (1.0 + rs)
    # avg_loss == 0 and avg_gain > 0  -> rs = inf -> rsi = 100 (handled by formula)
    # avg_loss == 0 and avg_gain == 0 -> flat window -> neutral 50
    flat = (avg_gain == 0.0) & (avg_loss == 0.0)
    rsi_d = np.where(flat, 50.0, rsi_d)
    out[1:] = rsi_d
    return out


def true_range(high, low, close) -> np.ndarray:
    """True range. ``tr[0]`` uses the first bar's high-low (no prior close)."""
    h, l, c = _as_float(high), _as_float(low), _as_float(close)
    prev_c = np.empty_like(c)
    prev_c[0] = np.nan
    prev_c[1:] = c[:-1]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    tr[0] = h[0] - l[0]
    return tr


def atr(high, low, close, n: int = 14) -> np.ndarray:
    """Average true range (Wilder). First valid value at index ``n-1``."""
    return _wilder_rma(true_range(high, low, close), n)


def adx(high, low, close, n: int = 14):
    """Average directional index. Returns (adx, plus_di, minus_di).

    Standard Wilder construction; the ADX line has a long warmup (~2n) as it is
    a smoothing of DX, which itself depends on smoothed DI.
    """
    h, l, c = _as_float(high), _as_float(low), _as_float(close)
    size = len(c)
    plus_di = np.full(size, np.nan)
    minus_di = np.full(size, np.nan)
    adx_out = np.full(size, np.nan)
    if size < 2:
        return adx_out, plus_di, minus_di

    up = h[1:] - h[:-1]
    dn = l[:-1] - l[1:]
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(h, l, c)[1:]  # diff-space: index j == original index j+1

    atr_d = _wilder_rma(tr, n)
    pdm_s = _wilder_rma(plus_dm, n)
    mdm_s = _wilder_rma(minus_dm, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100.0 * pdm_s / atr_d
        mdi = 100.0 * mdm_s / atr_d
        dx = 100.0 * np.abs(pdi - mdi) / (pdi + mdi)
    adx_d = _wilder_rma(dx, n)

    plus_di[1:] = pdi
    minus_di[1:] = mdi
    adx_out[1:] = adx_d
    return adx_out, plus_di, minus_di


def vwap(high, low, close, volume, n: int) -> np.ndarray:
    """Rolling volume-weighted average price over the last ``n`` bars."""
    h, l, c, vol = _as_float(high), _as_float(low), _as_float(close), _as_float(volume)
    typical = (h + l + c) / 3.0
    pv = typical * vol
    cpv = np.cumsum(pv)
    cv = np.cumsum(vol)
    size = len(c)
    out = np.full(size, np.nan)
    for i in range(n - 1, size):
        if i >= n:
            num = cpv[i] - cpv[i - n]
            den = cv[i] - cv[i - n]
        else:
            num = cpv[i]
            den = cv[i]
        out[i] = num / den if den != 0 else np.nan
    return out


def realized_vol(close, n: int, periods_per_year: float | None = None) -> np.ndarray:
    """Rolling realized volatility = std of log returns over ``n`` bars.

    If ``periods_per_year`` is given, the result is annualized by ``sqrt``.
    First valid value at index ``n``.
    """
    c = _as_float(close)
    size = len(c)
    out = np.full(size, np.nan)
    if size < 2:
        return out
    logret = np.full(size, np.nan)
    logret[1:] = np.diff(np.log(c))
    for i in range(n, size):
        out[i] = np.std(logret[i - n + 1:i + 1], ddof=0)
    if periods_per_year:
        out = out * np.sqrt(periods_per_year)
    return out
