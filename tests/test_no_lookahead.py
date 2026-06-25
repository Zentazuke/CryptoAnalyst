"""No-look-ahead (causality) tests.

The defining trust property: a metric at index ``i`` must depend only on inputs
at indices ``<= i``. We verify this directly — computing an indicator on a
prefix of the data must reproduce, exactly, the values it produced on the full
series. If appending future bars ever changed a past value, that is a bug.
"""
from __future__ import annotations

import numpy as np

from analyst.features import indicators as ind
from analyst.features.engine import _macd


def assert_causal(fn, arrays: list[np.ndarray]) -> None:
    """`fn(*arrays) -> ndarray`; check prefix-stability at several cut points."""
    full = fn(*arrays)
    length = len(arrays[0])
    for k in (length // 2, length - 25, length - 1, length):
        if k < 2:
            continue
        partial = fn(*[a[:k] for a in arrays])
        head = full[:k]
        # identical finiteness pattern: a prefix reveals no fewer/more values
        assert np.array_equal(np.isfinite(head), np.isfinite(partial)), (
            f"{fn} changed which values are defined at cut {k}"
        )
        mask = np.isfinite(head)
        np.testing.assert_allclose(
            partial[mask], head[mask], rtol=1e-12, atol=1e-12,
            err_msg=f"{fn} changed a past value at cut {k}",
        )


def test_single_input_indicators_are_causal(ohlc):
    c = ohlc["close"]
    assert_causal(lambda x: ind.sma(x, 20), [c])
    assert_causal(lambda x: ind.ema(x, 20), [c])
    assert_causal(lambda x: ind.rsi(x, 14), [c])
    assert_causal(lambda x: ind.rolling_std(x, 20), [c])
    assert_causal(lambda x: ind.realized_vol(x, 20), [c])


def test_bollinger_outputs_are_causal(ohlc):
    c = ohlc["close"]
    for idx in range(4):  # mid, upper, lower, bandwidth
        assert_causal(lambda x, i=idx: ind.bollinger(x, 20)[i], [c])


def test_macd_outputs_are_causal(ohlc):
    c = ohlc["close"]
    for idx in range(3):  # line, signal, hist
        assert_causal(lambda x, i=idx: _macd(x, 12, 26, 9)[i], [c])


def test_ohlc_indicators_are_causal(ohlc):
    h, l, c, v = ohlc["high"], ohlc["low"], ohlc["close"], ohlc["volume"]
    assert_causal(lambda hh, ll, cc: ind.true_range(hh, ll, cc), [h, l, c])
    assert_causal(lambda hh, ll, cc: ind.atr(hh, ll, cc, 14), [h, l, c])
    assert_causal(lambda hh, ll, cc, vv: ind.vwap(hh, ll, cc, vv, 20), [h, l, c, v])
    for idx in range(3):  # adx, plus_di, minus_di
        assert_causal(lambda hh, ll, cc, i=idx: ind.adx(hh, ll, cc, 14)[i], [h, l, c])
