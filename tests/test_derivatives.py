"""Causal alignment of funding to candle bars."""
from __future__ import annotations

import numpy as np

from analyst.regime.derivatives import align_funding, funding_features

HOUR = 3_600_000


def test_align_is_causal_forward_fill():
    candle_ts = [1000, 2000, 3000, 4000]
    funding = [{"t": 1500, "v": 0.1}, {"t": 3500, "v": 0.2}]
    out = align_funding(candle_ts, funding)
    # ts 1000: nothing yet -> nan ; 2000,3000: 0.1 ; 4000: 0.2
    assert np.isnan(out[0])
    assert out[1] == 0.1 and out[2] == 0.1
    assert out[3] == 0.2


def test_align_never_uses_future_value():
    candle_ts = [1000, 2000]
    funding = [{"t": 5000, "v": 0.9}]  # only future funding
    out = align_funding(candle_ts, funding)
    assert np.all(np.isnan(out))  # never pulled the future value back


def test_funding_features_keys_and_length():
    candles = [{"ts": i * HOUR, "close": 100.0} for i in range(300)]
    funding = [{"t": i * HOUR, "v": 0.0001 * ((-1) ** i)} for i in range(300)]
    feats = funding_features(candles, funding)
    assert set(feats) == {"funding_rate", "funding_rank", "funding_chg"}
    assert all(len(v) == 300 for v in feats.values())
