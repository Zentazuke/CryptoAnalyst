"""Generate the engine's measured model card.

One auditable place that answers "what does this engine actually do, measured?"
For each symbol x timeframe it reports the regime calibration (per-label hit-rate
+ CI + significance), the calibrated ensemble's out-of-sample edge, the
funding-crowding contrarian edge, and (per symbol) the on-chain divergence edge.
Everything is the engine's own causal, no-look-ahead calibration — this script
just collects and formats it.

Run (with the API/scheduler down so the DB is readable):
    python -m scripts.model_card                 # prints + writes MODEL_CARD.md
    python -m scripts.model_card --stdout-only
"""
from __future__ import annotations

import argparse
import datetime as dt

from analyst.commentary import DEFAULT_HORIZON
from analyst.config import DB_PATH
from analyst.crowd import calibrate_funding_contrarian
from analyst.ensemble import ensemble_read
from analyst.onchain_calibration import calibrate_onchain_divergence
from analyst.regime import classifier as C
from analyst.regime.calibration import calibrate
from analyst.storage import Store

SYMBOLS = ["BTC_USDT", "ETH_USDT"]
TIMEFRAMES = ["1h", "4h", "1D"]
VERDICT = {"edge": "**EDGE**", "negative": "worse-than-chance", "no-edge": "no edge",
           "insufficient": "insufficient n", "no-data": "no data"}


def _fmt(cal: dict | None) -> str:
    """Format a calibration/evidence dict into one compact, honest cell."""
    if not cal or cal.get("hit_rate") is None:
        return "—"
    hit = cal["hit_rate"] * 100
    base = (cal.get("base_rate") or 0) * 100
    ci = ""
    if cal.get("ci_low") is not None and cal.get("ci_high") is not None:
        ci = f" [{cal['ci_low'] * 100:.0f}–{cal['ci_high'] * 100:.0f}]"
    lift = f" ·{cal['lift']:.2f}×" if cal.get("lift") is not None else ""
    n = cal.get("n") or cal.get("count")
    return f"{hit:.0f}%{ci} vs {base:.0f}%{lift} · {VERDICT.get(cal.get('verdict'), '?')} (n={n})"


def build(store: Store) -> str:
    out: list[str] = []
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out.append("# Crypto Analyst — Model Card\n")
    out.append(f"_Auto-generated {now} from the live engine calibrations. Every figure is causal "
               "(no look-ahead) and reported with a Wilson 95% CI; an edge is only called real when "
               "the interval excludes the base rate._\n")

    for sym in SYMBOLS:
        out.append(f"\n## {sym.replace('_', '/')}\n")

        # ---- regime, per timeframe ----
        out.append("### Regime calibration (per directional label)\n")
        out.append("| Timeframe | Horizon | trend_up | trend_down | range |")
        out.append("|---|---|---|---|---|")
        for tf in TIMEFRAMES:
            rows = store.get_candles(sym, tf)
            if len(rows) < 120:
                out.append(f"| {tf} | — | _insufficient history_ |||")
                continue
            h = DEFAULT_HORIZON.get(tf, 12)
            rep = calibrate(rows, params={"horizon": h})["per_label"]
            out.append(f"| {tf} | {h} | {_fmt(rep.get(C.TREND_UP))} | "
                       f"{_fmt(rep.get(C.TREND_DOWN))} | {_fmt(rep.get(C.RANGE))} |")

        # ---- ensemble, per timeframe ----
        out.append("\n### Calibrated ensemble — out-of-sample directional edge\n")
        out.append("| Timeframe | Lean now | Out-of-sample track record |")
        out.append("|---|---|---|")
        for tf in TIMEFRAMES:
            rows = store.get_candles(sym, tf)
            er = ensemble_read(rows, tf)
            if not er:
                out.append(f"| {tf} | — | _insufficient history_ |")
                continue
            out.append(f"| {tf} | {er['lean']} | {_fmt(er.get('calibration'))} |")

        # ---- per-symbol signals ----
        out.append("\n### Other measured signals\n")
        funding = store.get_funding(sym)
        rows_1h = store.get_candles(sym, "1h")
        crowd = calibrate_funding_contrarian(rows_1h, funding, DEFAULT_HORIZON.get("1h", 24)) if funding else None
        onc = calibrate_onchain_divergence(sym, horizon=10)
        out.append(f"- **Funding-crowding contrarian (1h):** {_fmt(crowd)}")
        out.append(f"- **On-chain divergence (10d):** {_fmt(onc)}")

    out.append("\n---\n")
    out.append("**Reading it:** `EDGE` = the 95% CI excludes the base rate (a statistically real, if "
               "often small, edge). `no edge` = within noise. `insufficient n` = too few samples to "
               "judge. The honest headline of the project holds: single short-horizon signals sit near "
               "the predictability floor; measured value concentrates in trend/confluence on higher "
               "timeframes.\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--out", default="MODEL_CARD.md")
    ap.add_argument("--stdout-only", action="store_true")
    args = ap.parse_args()
    with Store(args.db, read_only=True) as store:
        report = build(store)
    print(report)
    if not args.stdout_only:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n[wrote {args.out}]")


if __name__ == "__main__":
    main()
