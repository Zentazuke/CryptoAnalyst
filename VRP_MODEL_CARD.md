# VRP Strategy — Model Card

_The one validated, non-directional edge this project found: harvesting the
volatility risk premium (selling implied vol that trades above realized),
defined-risk. Every figure is causal, costs-included, and stress-tested._

## The strategy
- **Sell vol** (short a vol/variance position) when implied (Deribit **DVOL**) is
  above expected realized — which it is, structurally, ~70% of the time.
- **Monthly, 30-day hold** — this *must* match DVOL's 30-day tenor; shorter holds
  mismatch the implied horizon and produce fake edge.
- **Defined-risk** — cap each trade's loss (~−12 vol-pts) by selling a spread /
  buying a far tail hedge (~1.5 vol-pts cost). The premium is the edge; the
  *structure*, not timing, manages the tail (an entry-time risk gate does **not**
  help — crashes arrive from calm).

## Measured performance (~5y, 63 non-overlapping monthly trades, net of 2 vol-pt cost)

| Asset | Sharpe (95% CI) | First half | Second half | Cost 1→4 | Beats placebo | Verdict |
|---|---|---|---|---|---|---|
| **BTC** | **+1.79** [+0.87, +2.71] | +2.19 | +1.12 | 1.98 → 1.39 | 85% | **robust — tradeable** |
| ETH | +1.20 [+0.31, +2.09] | +2.09 | +0.34 | 1.36 → 0.88 | 34% | **fails — drop** |

- **BTC** is positive in *both* sub-periods and survives cost stress → a real,
  stable, structural edge.
- **ETH** concentrated in 2021–23 and faded to ~0 in 2024–26, and is
  indistinguishable from a DVOL-shuffle placebo → not a reliable standalone
  strategy. The earlier ETH "rescue" was the tail-cap mechanically helping any
  short-vol, not an ETH premium.

## What does NOT work (tested, negative)
- **Forecasting realized vol** to time it — HAR doesn't robustly beat persistence
  (the winner flips between coins); and you don't need it, the premium is a
  *level* edge.
- **An analyst risk-state gate** on entries — lowers the Sharpe; crashes enter
  from calm, and "risk-off when vol is high" skips the richest post-scare trades.

## Honest caveats
- **Vol-swap proxy, not a real option chain.** Skew makes the tail hedge dearer
  and the left tail fatter than modeled → real net edge is thinner than shown.
- **Small sample** — 63 monthly trades; even BTC's CI spans ~[0.9, 2.7].
- **Tenor discipline** — only the 30-day horizon is valid against DVOL.
- **Execution** — requires Deribit options; live frictions (spreads, slippage,
  margin) exceed the 2 vol-pt assumption.

## The analyst's role
Not to predict the premium (it can't beat costs) but to **frame and monitor** it:
current DVOL vs forecast realized, the premium percentile (rich / fair / cheap),
and the defined-risk levels. The cockpit for the one strategy that works.
