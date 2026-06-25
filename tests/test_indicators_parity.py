"""Reference-parity vs TA-Lib (the gold standard) and pandas primitives.

TA-Lib parity is skipped if the library is unavailable, so the suite still runs
everywhere; where TA-Lib is present (incl. our dev/CI env), RSI/MACD/ATR and the
rest are checked against it directly.

Smoothed indicators (EMA/RSI/ATR/ADX/MACD) use recursive seeding whose initial
transient differs by convention between implementations but decays geometrically;
we therefore compare on the *stabilized* region, where all conventions agree.
"""
from __future__ import annotations

import numpy as np
import pytest

from analyst.features import indicators as ind
from analyst.features.engine import _macd

talib = pytest.importorskip("talib")

STAB = 200  # compare from here on (series is 300 bars): transient has decayed


def _both_finite_close(a, b, lo=STAB, rtol=1e-4, atol=1e-4):
    a, b = a[lo:], b[lo:]
    assert np.all(np.isfinite(a)), "our series has NaNs in the stabilized region"
    assert np.all(np.isfinite(b)), "reference has NaNs in the stabilized region"
    np.testing.assert_allclose(a, b, rtol=rtol, atol=atol)


def test_sma_exact_vs_talib(ohlc):
    c = ohlc["close"]
    mine, ref = ind.sma(c, 20), talib.SMA(c, 20)
    m = np.isfinite(ref)
    np.testing.assert_allclose(mine[m], ref[m], rtol=1e-9, atol=1e-9)


def test_bbands_exact_vs_talib(ohlc):
    c = ohlc["close"]
    mid, upper, lower, _ = ind.bollinger(c, 20, 2.0)
    u, m_, l = talib.BBANDS(c, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    fin = np.isfinite(m_)
    np.testing.assert_allclose(mid[fin], m_[fin], rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(upper[fin], u[fin], rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(lower[fin], l[fin], rtol=1e-9, atol=1e-9)


def test_ema_vs_talib(ohlc):
    c = ohlc["close"]
    _both_finite_close(ind.ema(c, 20), talib.EMA(c, 20))


def test_rsi_vs_talib(ohlc):
    c = ohlc["close"]
    _both_finite_close(ind.rsi(c, 14), talib.RSI(c, 14))


def test_atr_vs_talib(ohlc):
    h, l, c = ohlc["high"], ohlc["low"], ohlc["close"]
    _both_finite_close(ind.atr(h, l, c, 14), talib.ATR(h, l, c, 14))


def test_macd_vs_talib(ohlc):
    c = ohlc["close"]
    line, signal, hist = _macd(c, 12, 26, 9)
    t_line, t_signal, t_hist = talib.MACD(c, 12, 26, 9)
    _both_finite_close(line, t_line)
    _both_finite_close(signal, t_signal)
    _both_finite_close(hist, t_hist)


def test_adx_vs_talib(ohlc):
    h, l, c = ohlc["high"], ohlc["low"], ohlc["close"]
    adx_v, plus_di, minus_di = ind.adx(h, l, c, 14)
    _both_finite_close(adx_v, talib.ADX(h, l, c, 14))
    _both_finite_close(plus_di, talib.PLUS_DI(h, l, c, 14))
    _both_finite_close(minus_di, talib.MINUS_DI(h, l, c, 14))


def test_sma_matches_pandas(ohlc):
    pd = pytest.importorskip("pandas")
    c = ohlc["close"]
    ref = pd.Series(c).rolling(20).mean().to_numpy()
    m = np.isfinite(ref)
    np.testing.assert_allclose(ind.sma(c, 20)[m], ref[m], rtol=1e-12, atol=1e-12)


def test_rolling_std_matches_pandas(ohlc):
    pd = pytest.importorskip("pandas")
    c = ohlc["close"]
    ref = pd.Series(c).rolling(20).std(ddof=0).to_numpy()
    m = np.isfinite(ref)
    np.testing.assert_allclose(ind.rolling_std(c, 20)[m], ref[m], rtol=1e-12, atol=1e-12)
