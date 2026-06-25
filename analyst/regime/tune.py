"""Walk-forward threshold tuning for the regime classifier.

Objective = count-weighted *excess hit* over the actionable labels:
    sum_label count * (hit_rate - base_rate) / sum_label count
i.e. how much better than chance the classifier's calls resolve. We optimise on
a TRAIN split and report the chosen params' performance on a held-out TEST
split, alongside the default params on the same TEST split — so any improvement
is out-of-sample, not curve-fit.
"""
from __future__ import annotations

import argparse
from itertools import product
from typing import Any

from analyst.config import DB_PATH
from analyst.regime import classifier as C
from analyst.regime.calibration import calibrate
from analyst.storage import Store

ACTIONABLE = [C.TREND_UP, C.TREND_DOWN, C.BREAKOUT, C.LOW_VOL_DRIFT, C.FLASH_RISK]

DEFAULT_GRID: dict[str, list] = {
    "adx_trend": [22.0, 25.0, 28.0],
    "adx_range": [18.0, 20.0],
    "flash_ret_atr": [2.5, 3.0, 3.5],
    "donchian_n": [15, 20, 30],
}


def objective(report: dict, labels: list[str] = ACTIONABLE) -> float:
    num = den = 0.0
    for lab in labels:
        st = report["per_label"].get(lab)
        if st and st["count"] and st["hit_rate"] is not None and st["base_rate"] is not None:
            num += st["count"] * (st["hit_rate"] - st["base_rate"])
            den += st["count"]
    return num / den if den else 0.0


def evaluate(candles: list[Any], class_params: dict, calib_params: dict) -> tuple[float, dict]:
    results = C.classify_series(candles, class_params)
    report = calibrate(candles, results, calib_params)
    return objective(report), report


def grid_search(candles: list[Any], grid: dict, calib_params: dict) -> list[tuple[float, dict]]:
    keys = list(grid)
    scored = []
    for combo in product(*grid.values()):
        cp = dict(zip(keys, combo))
        obj, _ = evaluate(candles, cp, calib_params)
        scored.append((obj, cp))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def walk_forward(
    candles: list[Any],
    grid: dict | None = None,
    calib_params: dict | None = None,
    split: float = 0.5,
) -> dict:
    grid = grid or DEFAULT_GRID
    calib_params = calib_params or {"horizon": 24}
    k = int(len(candles) * split)
    train, test = candles[:k], candles[k:]

    scored = grid_search(train, grid, calib_params)
    best_obj, best = scored[0]
    test_obj, test_report = evaluate(test, best, calib_params)
    default_obj, default_report = evaluate(test, {}, calib_params)

    return {
        "best_params": best,
        "train_obj": round(best_obj, 5),
        "test_obj": round(test_obj, 5),
        "default_test_obj": round(default_obj, 5),
        "test_report": test_report,
        "default_report": default_report,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Walk-forward regime threshold tuning.")
    ap.add_argument("--symbol", default="BTC_USDT")
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    with Store(args.db, read_only=True) as store:
        rows = store.get_candles(args.symbol, args.timeframe)
    if not rows:
        print(f"no {args.timeframe} data for {args.symbol}")
        return

    out = walk_forward(rows, calib_params={"horizon": args.horizon})
    print(f"=== walk-forward tuning {args.symbol} {args.timeframe} (h={args.horizon}, bars={len(rows)}) ===")
    print("best params (chosen on TRAIN):", out["best_params"])
    print(f"objective  train={out['train_obj']:+.4f}  test(tuned)={out['test_obj']:+.4f}  "
          f"test(default)={out['default_test_obj']:+.4f}")
    improved = out["test_obj"] > out["default_test_obj"]
    print("OOS verdict:", "tuned beats default" if improved else "no OOS improvement (keep default)")
    print("\nTEST per-label lift (tuned):")
    for lab in ACTIONABLE + [C.RANGE]:
        st = out["test_report"]["per_label"].get(lab, {})
        if st.get("count"):
            print(f"  {lab:14} n={st['count']:<5} hit={st['hit_rate']}  base={st['base_rate']}  lift={st['lift']}")


if __name__ == "__main__":
    main()
