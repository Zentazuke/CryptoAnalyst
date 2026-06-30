# VRP Strategy — Model Card

_The variance risk premium is the only edge this project couldn't disprove. It is
**real but not cleanly harvestable by a retail, defined-risk trader.** This card
states that honestly — corrected after a real structure-level backtest replaced
the optimistic proxy._

## The premium is real (this part holds)
On BTC, implied vol (Deribit **DVOL**) sits systematically above the realized vol
that follows:
- implied > realized **~74% of days**, by **~+9.7 vol-points** on average,
- stable across both halves of ~5 years, not a reshuffling fluke,
- structural, not predictive — you're paid to bear tail risk, like an insurer.

## But the tradeable version loses (this corrects the earlier claim)
An earlier version of this card reported a defined-risk Sharpe of **~1.8**. That
was a **frictionless proxy** (a continuously delta-hedged variance swap) — and it
was **wrong as a retail trade**. The real structure-level backtest (a monthly,
DVOL-priced **iron condor** with the actual capped payoff, fees included) comes
out **net-negative across strikes and tenors: Sharpe −0.04 to −0.8**, an 82–91%
win rate masking a few **−100% capped tails** that wipe out the small wins.

The tell: **even priced at realized vol (zero premium), the static condor loses
~−5%/cycle** — because crypto's endpoints are fatter-tailed than daily vol
predicts, so a static short structure held to expiry gets run over by jumps. The
~+2.5%/cycle premium can't cover the fat-tail drag.

## The reconciliation
| | what it is | result |
|---|---|---|
| Proxy (~1.8 Sharpe) | continuously **delta-hedged variance swap** | harvests implied−realized regardless of the endpoint |
| Tradeable condor (−0.04 to −0.8) | **static endpoint bet**, held to expiry | the fat tail kills it |

The only thing that monetizes the premium cleanly is a **delta-hedged short
straddle (rehedged daily)** — the operationally-intensive, gap-risky
institutional version. A small trader selling vol they can't continuously hedge
is exactly how blow-ups happen.

## Verdict
**Context, not a trade signal.** The VRP read in the analyst (DVOL vs realized,
the premium percentile, rich/fair/cheap) is a *true market observable* worth
watching — but "rich" is **not** a green light to sell vol. Retail defined-risk
structures don't harvest it; delta-hedged variance does, and that's out of scope
for this tool. Treat the cockpit as a gauge, never as a trade.

## What does NOT work (tested, negative)
- Forecasting realized vol to time it (HAR doesn't robustly beat persistence).
- An analyst risk-state gate on entries (crashes enter from calm).
- The retail defined-risk harvest itself (above).
