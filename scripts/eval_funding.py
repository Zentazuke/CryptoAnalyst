"""Does funding history add regime accuracy? Honest walk-forward A/B.

Compares, out-of-sample, three predictors of the vol-scaled forward outcome:
  - rules            (rule-based classifier, price-only)
  - ML price-only    (HistGBM on price/TA features)
  - ML price+funding (same model + funding level/rank/slope features)

    python scripts/eval_funding.py --symbol BTC_USDT --timeframe 1h --horizon 24
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root on path

from analyst.config import DB_PATH
from analyst.regime.derivatives import funding_features
from analyst.regime.model import walk_forward_eval
from analyst.storage import Store


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC_USDT")
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    with Store(args.db, read_only=True) as store:
        candles = store.get_candles(args.symbol, args.timeframe)
        funding = store.get_funding(args.symbol)

    if not candles:
        print(f"no {args.timeframe} candles for {args.symbol}")
        return
    if not funding:
        print(f"no funding history for {args.symbol} — run `python -m analyst.collect_funding`")
        return

    base = walk_forward_eval(candles, horizon=args.horizon)
    feats = funding_features(candles, funding)
    enriched = walk_forward_eval(candles, horizon=args.horizon, extra_features=feats)

    print(f"=== funding A/B {args.symbol} {args.timeframe} h={args.horizon} "
          f"(candles={len(candles)}, funding={len(funding)}, oos={base['oos_samples']}) ===")
    print(f"  rules            balanced_acc = {base['rule_balanced_acc']}")
    print(f"  ML price-only    balanced_acc = {base['ml_balanced_acc']}  ({base['n_features']} feats)")
    print(f"  ML price+funding balanced_acc = {enriched['ml_balanced_acc']}  ({enriched['n_features']} feats)")
    print(f"  chance           balanced_acc = {base['chance_balanced_acc']}")
    delta = enriched["ml_balanced_acc"] - base["ml_balanced_acc"]
    print(f"\n  funding delta (ML): {delta:+.4f}  ->",
          "funding HELPS" if delta > 0 else "funding does not help")
    beats_rules = enriched["ml_balanced_acc"] > base["rule_balanced_acc"]
    print("  vs rules:", "ML+funding beats rules" if beats_rules else "rules still competitive")
    print("\n  per-class recall ML price+funding:", enriched["ml_recall"])


if __name__ == "__main__":
    main()
