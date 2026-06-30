# Strategy Graveyard

_What's been tested and disproven, so we don't re-chase it. Ported from the
Kronos failed-strategies postmortem (testnet/backtest figures; no real capital
risked). One root cause killed almost everything: at the frequencies tried, the
directional signal was always thinner than the ~15–20 bps round-trip cost._

| Strategy | What it was | Best honest result | Verdict |
|---|---|---|---|
| Kronos ML (core) | small ML price predictor | 47–49% win, Sharpe −0.04 to −0.09 | **DEAD** — never cracked 50% |
| Kelly / meta-labeler | logistic P(win) filter | anti-predictive (33% vs 62% base) | **DEAD** |
| Entry-rule search | mined 2–3 condition combos | 4 "greens", OOS 0.07–0.27, never replicated | **DEAD** — data-mining noise |
| Consensus TA board | 7-indicator trend net-bias | 48% win at 1:1 over 5mo | **DEAD** — lost money with the signal |
| RSI-2 reversion | Connors fade-the-extreme | no breadth+persistence survivor net of fees | **DEAD** — didn't clear cost wall |
| OFI (order-flow) | queue-change signal | net-negative taker; maker adversely selected | **DEAD** — edge < spread |
| Lead-lag | alt vs BTC-implied move | raw lead ≈ 0 (~15s); catch-up failed OOS | **DEAD** — too fast |
| Funding carry | delta-neutral spot/perp | ~19%/yr headline; net thin, tail-risky | **SET ASIDE** — compressing |
| Pairs / stat-arb | cointegration reversion | beat passive on paper; OOS weak | **SET ASIDE** — marginal after costs |
| **VRP** | sell overpriced implied vol | premium REAL (implied>realized 74%); retail defined-risk condor LOSES (Sharpe −0.04 to −0.8) | **REAL edge, not cleanly harvestable retail** |
| Crypto-Analyst as alpha | regime/ensemble to gate or trade | gates failed placebo (p=0.18/0.36); swing failed breadth (2/7 coins) | **DEAD as alpha** — its own model card agrees |
| Intraday-TSM | session momentum | +16% 1yr → −17% / −52% DD over 5yr | **failed backtest** (live forward only) |
| Stablecoin-flow | on-chain supply timing | Sharpe 1.3 1yr → −0.17 5yr | **DEAD** — regime luck |

## The meta-lesson (the analyst's whole reason to exist)
The most reliable tell across all of it: the **in-sample → out-of-sample collapse**
and the **proxy → tradeable collapse**. Rule search 86%→53%. Intraday +16%→−17%.
Stablecoin 1.3→−0.17. Analyst gate "OOS 1.0"→placebo p=0.18. VRP proxy 1.8→
tradeable-negative. Every exciting number was a small sample, an in-sample fit,
or a frictionless proxy; every honest OOS / placebo / breadth / real-friction
test evaporated the edge.

**Refusing to trust the flattering number is the most valuable thing this project
produced.** The analyst's job is to keep producing that refusal — see
`VRP_MODEL_CARD.md` (the premium is real but un-harvestable retail) and
`SIGNAL_CARD.md` (which signals carry measured, stable directional edge — modest,
~1.2 lift, costs-bound).
