"""Golden-vector tests: hand-computed expected values for our conventions."""
from __future__ import annotations

import numpy as np

from analyst.features import indicators as ind


def test_sma_golden():
    out = ind.sma([1, 2, 3, 4, 5], 3)
    expected = [np.nan, np.nan, 2.0, 3.0, 4.0]
    np.testing.assert_allclose(out, expected)


def test_ema_golden_sma_seeded():
    # seed = mean(1,2,3) = 2 at index 2; alpha = 0.5
    # idx3 = .5*4 + .5*2 = 3 ; idx4 = .5*5 + .5*3 = 4
    out = ind.ema([1, 2, 3, 4, 5], 3)
    np.testing.assert_allclose(out, [np.nan, np.nan, 2.0, 3.0, 4.0])


def test_atr_golden():
    high = [10, 11, 12]
    low = [8, 9, 9]
    close = [9, 10, 11]
    # TR0 = 10-8 = 2 ; TR1 = max(2,2,0)=2 ; TR2 = max(3,2,1)=3
    # ATR(n=2): idx1 = mean(2,2)=2 ; idx2 = (2*1 + 3)/2 = 2.5
    out = ind.atr(high, low, close, 2)
    np.testing.assert_allclose(out, [np.nan, 2.0, 2.5])


def test_rsi_golden():
    # values=[10,11,10,11,12], n=2
    # deltas +1,-1,+1,+1 ; gains 1,0,1,1 ; losses 0,1,0,0
    # avg_gain: .5, .75, .875 ; avg_loss: .5, .25, .125
    # rs: 1, 3, 7 -> rsi 50, 75, 87.5  (aligned to v indices 2,3,4)
    out = ind.rsi([10, 11, 10, 11, 12], 2)
    np.testing.assert_allclose(out, [np.nan, np.nan, 50.0, 75.0, 87.5])


def test_bollinger_relationships(ohlc):
    close = ohlc["close"]
    mid, upper, lower, bw = ind.bollinger(close, 20, 2.0)
    # middle band is exactly the SMA
    np.testing.assert_allclose(mid, ind.sma(close, 20), equal_nan=True)
    # band is symmetric around the middle; width = (upper-lower)/mid
    np.testing.assert_allclose(upper - mid, mid - lower, equal_nan=True)
    finite = np.isfinite(bw)
    np.testing.assert_allclose(bw[finite], ((upper - lower) / mid)[finite])


def test_macd_is_difference_of_emas(ohlc):
    from analyst.features.engine import _macd

    close = ohlc["close"]
    macd_line, _, hist = _macd(close, 12, 26, 9)
    expected_line = ind.ema(close, 12) - ind.ema(close, 26)
    np.testing.assert_allclose(macd_line, expected_line, equal_nan=True)
