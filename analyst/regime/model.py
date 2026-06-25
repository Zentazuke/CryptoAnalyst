"""Trees-first ML regime model with honest walk-forward evaluation.

Target: the realized, *volatility-scaled* forward outcome over ``horizon`` bars,
    scaled = (close[i+H]/close[i] - 1) / (atr%[i] * sqrt(H))
    up   if scaled >  k ;  down if scaled < -k ;  else range
Features: the causal regime features (price levels converted to scale-free
distances). The model only ever sees causal features at bar i; labels are known
only in hindsight (standard supervised setup).

Evaluation is strictly out-of-sample via expanding-window TimeSeriesSplit, and
is compared head-to-head with the rule-based classifier mapped to the same three
classes. We only consider the model an upgrade if it beats the rules OOS.
"""
from __future__ import annotations

import argparse
import math
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import TimeSeriesSplit

from analyst.config import DB_PATH
from analyst.regime import classifier as C
from analyst.regime.features import compute_regime_features
from analyst.storage import Store

CLASSES = ["down", "range", "up"]
MODEL_FEATURES = [
    "adx", "plus_di", "minus_di", "ema_slope", "bb_bandwidth", "bandwidth_chg",
    "atr_pct", "atr_pct_rank", "ret_atr", "vol_z", "donchian_hi_dist", "donchian_lo_dist",
]


def _new_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        class_weight="balanced",
        learning_rate=0.05,
        max_iter=300,
        max_depth=4,
        l2_regularization=1.0,
        random_state=0,
    )


def _feature_matrix(feats: dict[str, np.ndarray]) -> np.ndarray:
    close, atr_pct = feats["close"], feats["atr_pct"]
    denom = atr_pct * close + 1e-9
    cols = dict(feats)
    cols["donchian_hi_dist"] = (close - feats["donchian_hi"]) / denom
    cols["donchian_lo_dist"] = (close - feats["donchian_lo"]) / denom
    return np.column_stack([cols[name] for name in MODEL_FEATURES])


def build_dataset(
    candles: list[Any], horizon: int = 24, k: float = 1.0, params: dict | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (X, y, idx): feature rows, class labels, and source bar indices."""
    feats = compute_regime_features(candles, params)
    X_all = _feature_matrix(feats)
    close, atr_pct = feats["close"], feats["atr_pct"]
    n = len(close)
    sqrt_h = math.sqrt(horizon)

    rows, ys, idxs = [], [], []
    for i in range(n - horizon):
        x = X_all[i]
        if not np.all(np.isfinite(x)) or not (np.isfinite(atr_pct[i]) and atr_pct[i] > 0 and close[i] > 0):
            continue
        scaled = (close[i + horizon] / close[i] - 1.0) / (atr_pct[i] * sqrt_h)
        ys.append("up" if scaled > k else "down" if scaled < -k else "range")
        rows.append(x)
        idxs.append(i)
    return np.array(rows, dtype=float), np.array(ys), np.array(idxs, dtype=int)


def _rule_class(label: str) -> str:
    if label == C.TREND_UP:
        return "up"
    if label == C.TREND_DOWN:
        return "down"
    return "range"  # range / low_vol_drift / breakout / flash_risk / unknown


def walk_forward_eval(
    candles: list[Any], horizon: int = 24, k: float = 1.0, n_splits: int = 5,
    params: dict | None = None,
) -> dict:
    """Out-of-sample model-vs-rules comparison via TimeSeriesSplit."""
    X, y, idx = build_dataset(candles, horizon, k, params)
    if len(y) < 250:
        raise ValueError(f"not enough samples ({len(y)}) for {n_splits}-fold walk-forward")

    rule_labels = [r.label for r in C.classify_series(candles, params)]
    rule_pred_all = np.array([_rule_class(rule_labels[i]) for i in idx])

    ml_true, ml_pred, rule_true, rule_pred = [], [], [], []
    for tr, te in TimeSeriesSplit(n_splits=n_splits).split(X):
        clf = _new_model()
        clf.fit(X[tr], y[tr])
        ml_pred.extend(clf.predict(X[te]))
        ml_true.extend(y[te])
        rule_pred.extend(rule_pred_all[te])
        rule_true.extend(y[te])

    ml_true = np.array(ml_true); ml_pred = np.array(ml_pred)
    rule_pred = np.array(rule_pred)

    def recall(true, pred, cls):
        m = true == cls
        return float((pred[m] == cls).mean()) if m.any() else None

    return {
        "horizon": horizon, "k": k, "n_splits": n_splits, "oos_samples": len(ml_true),
        "class_balance": {c: int((ml_true == c).sum()) for c in CLASSES},
        "ml_balanced_acc": round(balanced_accuracy_score(ml_true, ml_pred), 4),
        "rule_balanced_acc": round(balanced_accuracy_score(ml_true, rule_pred), 4),
        "chance_balanced_acc": round(1 / 3, 4),
        "ml_recall": {c: recall(ml_true, ml_pred, c) for c in CLASSES},
        "rule_recall": {c: recall(ml_true, rule_pred, c) for c in CLASSES},
    }


def train_and_predict_latest(
    candles: list[Any], horizon: int = 24, k: float = 1.0, params: dict | None = None
) -> dict | None:
    """Train on all labelled rows and return class probabilities for the last bar."""
    X, y, _ = build_dataset(candles, horizon, k, params)
    if len(y) < 250:
        return None
    clf = _new_model()
    clf.fit(X, y)
    x_last = _feature_matrix(compute_regime_features(candles, params))[-1]
    if not np.all(np.isfinite(x_last)):
        return None
    proba = clf.predict_proba(x_last.reshape(1, -1))[0]
    probs = {cls: round(float(p), 4) for cls, p in zip(clf.classes_, proba)}
    return {"probs": probs, "argmax": max(probs, key=probs.get)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Walk-forward ML-vs-rules regime evaluation.")
    ap.add_argument("--symbol", default="BTC_USDT")
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--k", type=float, default=1.0)
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    with Store(args.db, read_only=True) as store:
        rows = store.get_candles(args.symbol, args.timeframe)
    if not rows:
        print(f"no {args.timeframe} data for {args.symbol}")
        return

    rep = walk_forward_eval(rows, horizon=args.horizon, k=args.k)
    print(f"=== ML vs rules (walk-forward) {args.symbol} {args.timeframe} "
          f"h={args.horizon} bars={len(rows)} oos={rep['oos_samples']} ===")
    print("class balance (oos):", rep["class_balance"])
    print(f"balanced accuracy   ML={rep['ml_balanced_acc']}   "
          f"rules={rep['rule_balanced_acc']}   chance={rep['chance_balanced_acc']}")
    verdict = "ML beats rules OOS" if rep["ml_balanced_acc"] > rep["rule_balanced_acc"] else "rules competitive — keep rules"
    print("verdict:", verdict)
    print("per-class recall  ML  :", rep["ml_recall"])
    print("per-class recall  rules:", rep["rule_recall"])
    latest = train_and_predict_latest(rows, horizon=args.horizon, k=args.k)
    print("latest forecast:", latest)


if __name__ == "__main__":
    main()
