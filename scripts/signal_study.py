"""Which signals (and combinations) actually predict candle direction?

Ranks every candle-derived signal + combination by measured directional edge,
per timeframe, for BTC/ETH — with Wilson CIs, a significance verdict, and the
sub-period stability check that separates real edge from luck. Writes
SIGNAL_CARD.md.

    python -m scripts.signal_study
"""
from __future__ import annotations

import argparse
import datetime as dt

from analyst.config import DB_PATH
from analyst.signal_eval import evaluate_signals
from analyst.storage import Store

SYMBOLS = ["BTC_USDT", "ETH_USDT"]
TIMEFRAMES = ["1h", "4h", "1D"]


def _fmt(r) -> str:
    tag = "RELIABLE" if r["reliable"] else ("stable" if r["stable"] else
            ("significant" if r["significant"] else "—"))
    h1 = f"{r['h1_acc']*100:.0f}" if r["h1_acc"] is not None else "?"
    h2 = f"{r['h2_acc']*100:.0f}" if r["h2_acc"] is not None else "?"
    return (f"| {r['signal']:<24} | {r['n']:>4} | {r['accuracy']*100:4.0f}% "
            f"[{r['ci_low']*100:.0f}-{r['ci_high']*100:.0f}] | {r['base']*100:4.0f}% | "
            f"{(r['lift'] or 0):.2f} | {h1}/{h2} | {tag} |")


def build(store: Store) -> str:
    out = ["# Signal Calibration — directional edge by signal\n"]
    out.append(f"_Auto-generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC. "
               "Each signal's accuracy at calling the next move's direction (on vol-scaled "
               "significant moves), vs the majority-class baseline, with 95% CI and sub-period "
               "stability (first-half / second-half accuracy). **RELIABLE = significant AND positive "
               "in both halves.** Everything else is noise to discount._\n")
    for sym in SYMBOLS:
        out.append(f"\n## {sym.replace('_', '/')}\n")
        for tf in TIMEFRAMES:
            rows = store.get_candles(sym, tf)
            if len(rows) < 200:
                out.append(f"\n### {tf} — insufficient history\n")
                continue
            res = evaluate_signals(rows, tf)
            out.append(f"\n### {tf} (horizon {res['horizon']} bars)\n")
            out.append("| signal | n | accuracy [95% CI] | base | lift | H1/H2 | verdict |")
            out.append("|---|---|---|---|---|---|---|")
            for r in res["signals"]:
                out.append(_fmt(r))
    out.append("\n---\n**How to use:** rely on **RELIABLE** signals (significant edge that held in "
               "both halves); treat the rest as decoration. Note that even reliable directional edges "
               "here are small (lifts ~1.1-1.3) — consistent with the project finding that direction on "
               "liquid majors is near the predictability floor.\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--out", default="SIGNAL_CARD.md")
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
