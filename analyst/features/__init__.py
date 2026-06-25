"""Technical-analysis feature engine.

Pure, causal indicator functions (no look-ahead) plus a snapshot helper that
computes the standard set from stored candles. Conventions follow Wilder /
TA-Lib (SMA-seeded EMA, Wilder smoothing for RSI/ATR/ADX) so values are
verifiable against the TA-Lib reference.
"""
from analyst.features.engine import (  # noqa: F401
    INDICATOR_VERSION,
    compute_indicators,
    snapshot,
)
from analyst.features import indicators  # noqa: F401
