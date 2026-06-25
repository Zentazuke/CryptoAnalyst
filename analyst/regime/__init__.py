"""Regime classification: turn raw metrics into a transparent market-state call.

Labels: range · trend_up · trend_down · breakout · flash_risk · low_vol_drift.
Every call is causal (no look-ahead) and explains itself (contributing features
+ human-readable reasons). The calibration harness scores past calls against
realized forward outcomes so accuracy is measured, not asserted.
"""
from analyst.regime.classifier import (  # noqa: F401
    LABELS,
    RegimeResult,
    classify_latest,
    classify_series,
)
from analyst.regime.calibration import calibrate  # noqa: F401
from analyst.regime.features import compute_regime_features  # noqa: F401
