# Crypto Analyst — Model Card

_Auto-generated 2026-06-29 17:50 UTC from the live engine calibrations. Every figure is causal (no look-ahead) and reported with a Wilson 95% CI; an edge is only called real when the interval excludes the base rate._


## BTC/USDT

### Regime calibration (per directional label)

| Timeframe | Horizon | trend_up | trend_down | range |
|---|---|---|---|---|
| 1h | 24 | 9% [8–10] vs 8% ·1.08× · no edge (n=3458) | 10% [9–11] vs 8% ·1.25× · **EDGE** (n=4286) | 56% [54–57] vs 57% ·0.97× · worse-than-chance (n=6509) |
| 4h | 12 | 11% [10–12] vs 8% ·1.30× · **EDGE** (n=1850) | 6% [5–8] vs 7% ·0.94× · no edge (n=1800) | 60% [59–62] vs 60% ·1.01× · no edge (n=2950) |
| 1D | 5 | 10% [7–13] vs 8% ·1.30× · no edge (n=445) | 6% [4–9] vs 6% ·1.12× · no edge (n=493) | 61% [57–64] vs 63% ·0.97× · no edge (n=664) |

### Calibrated ensemble — out-of-sample directional edge

| Timeframe | Lean now | Out-of-sample track record |
|---|---|---|
| 1h | bullish | 59% [56–62] vs 56% ·1.05× · no edge (n=1168) |
| 4h | bullish | 61% [57–66] vs 56% ·1.09× · **EDGE** (n=450) |
| 1D | bearish | 66% [56–74] vs 53% ·1.24× · **EDGE** (n=96) |

### Other measured signals

- **Funding-crowding contrarian (1h):** 49% [48–50] vs 49% ·0.99× · no edge (n=14039)
- **On-chain divergence (10d):** 48% [43–53] vs 50% ·0.96× · no edge (n=336)

## ETH/USDT

### Regime calibration (per directional label)

| Timeframe | Horizon | trend_up | trend_down | range |
|---|---|---|---|---|
| 1h | 24 | 11% [10–12] vs 9% ·1.22× · **EDGE** (n=2326) | 9% [8–10] vs 8% ·1.13× · **EDGE** (n=3173) | 60% [59–62] vs 59% ·1.03× · **EDGE** (n=4494) |
| 4h | 12 | 13% [11–15] vs 8% ·1.58× · **EDGE** (n=1461) | 8% [7–9] vs 8% ·0.94× · no edge (n=2050) | 63% [61–64] vs 61% ·1.02× · no edge (n=2942) |
| 1D | 5 | 10% [8–14] vs 7% ·1.45× · **EDGE** (n=376) | 6% [5–9] vs 6% ·1.06× · no edge (n=587) | 63% [59–66] vs 62% ·1.02× · no edge (n=693) |

### Calibrated ensemble — out-of-sample directional edge

| Timeframe | Lean now | Out-of-sample track record |
|---|---|---|
| 1h | bullish | 56% [52–59] vs 56% ·0.99× · no edge (n=796) |
| 4h | bullish | 64% [59–68] vs 54% ·1.17× · **EDGE** (n=502) |
| 1D | bearish | 61% [51–70] vs 56% ·1.09× · no edge (n=95) |

### Other measured signals

- **Funding-crowding contrarian (1h):** 51% [50–52] vs 50% ·1.00× · no edge (n=9112)
- **On-chain divergence (10d):** 55% [51–59] vs 50% ·1.11× · **EDGE** (n=575)

---

**Reading it:** `EDGE` = the 95% CI excludes the base rate (a statistically real, if often small, edge). `no edge` = within noise. `insufficient n` = too few samples to judge. The honest headline of the project holds: single short-horizon signals sit near the predictability floor; measured value concentrates in trend/confluence on higher timeframes.

---

## Signal compatibility profile — regime classifier (added 2026-07-14)

Calibration numbers alone don't say WHO may consume a signal. Learned the hard
way (see STRATEGY_GRAVEYARD.md, grid entry): the regime signal's edge survives
only at turnover compatible with its horizon.

```
Signal horizon:     daily to multi-week
Information lag:    one causal daily shift (label for day D usable from D+1)
Expected decay:     slow
Suitable turnover:  low (~flips per month, not per day)

Suitable consumers: position sleeves · allocation shifts · risk scaling ·
                    slow rebalancing · exposure reduction / rotation
Poor consumers:     intraday grids · high-frequency inventory resets ·
                    rapid regime switching · fee-sensitive execution
```

Evidence: identical labels power the sleeve shadow test (low turnover —
beating buy-and-hold live) and failed to rescue the grid (high turnover —
every gate mode negative). Any NEW consumer of this signal must state its
expected turnover and show the edge survives its own friction before going
live. Every future calibrated signal added to this card should ship with the
same profile block.

**Confidence semantics (learned 2026-07-14, sleeve consumption study):** the
regime signal's confidence field carries information about HOW MUCH risk to
carry, not permission to trade MORE OFTEN. Used as a slow exposure scaler
(TR-A) it improved risk-adjusted results (basket Sharpe 1.17 vs 1.06, DD 19%
vs 23%); used to drive higher transaction frequency (vol-targeting variants,
thousands of micro-rebalances) the same information was consumed by friction.
Consumers may scale WITH confidence; they may not churn BECAUSE of it.
