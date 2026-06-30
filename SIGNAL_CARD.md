# Signal Calibration — directional edge by signal

_Auto-generated 2026-06-30 13:57 UTC. Each signal's accuracy at calling the next move's direction (on vol-scaled significant moves), vs the majority-class baseline, with 95% CI and sub-period stability (first-half / second-half accuracy). **RELIABLE = significant AND positive in both halves.** Everything else is noise to discount._


## BTC/USDT


### 1h (horizon 24 bars)

| signal | n | accuracy [95% CI] | base | lift | H1/H2 | verdict |
|---|---|---|---|---|---|---|
| regime                   | 1136 |   66% [63-68] |   52% | 1.25 | 63/69 | RELIABLE |
| COMBO regime+adx_di      | 1136 |   66% [63-68] |   52% | 1.25 | 63/69 | RELIABLE |
| COMBO all-agree          |  653 |   63% [59-66] |   51% | 1.24 | 59/67 | RELIABLE |
| COMBO ema_trend+regime   |  983 |   64% [61-67] |   53% | 1.22 | 60/68 | RELIABLE |
| adx_di                   | 1879 |   60% [57-62] |   50% | 1.18 | 59/60 | RELIABLE |
| COMBO adx_di+rsi_momentum | 1360 |   59% [56-61] |   51% | 1.15 | 60/57 | RELIABLE |
| rsi_momentum             | 1821 |   58% [56-60] |   51% | 1.14 | 58/58 | RELIABLE |
| COMBO majority(>=2)      | 2430 |   56% [54-58] |   51% | 1.11 | 55/57 | significant |
| ema_trend                | 2788 |   55% [53-56] |   50% | 1.09 | 54/55 | significant |
| bb_position              | 2788 |   53% [51-55] |   50% | 1.05 | 52/54 | significant |
| COMBO ema_trend+macd     | 2126 |   53% [51-55] |   50% | 1.05 | 52/53 | significant |
| macd                     | 2788 |   49% [48-51] |   50% | 0.98 | 49/50 | — |

### 4h (horizon 12 bars)

| signal | n | accuracy [95% CI] | base | lift | H1/H2 | verdict |
|---|---|---|---|---|---|---|
| COMBO all-agree          |  287 |   66% [60-71] |   57% | 1.14 | 73/57 | RELIABLE |
| COMBO ema_trend+macd     |  852 |   64% [61-67] |   57% | 1.12 | 65/63 | RELIABLE |
| bb_position              | 1217 |   62% [59-64] |   55% | 1.12 | 62/61 | RELIABLE |
| COMBO majority(>=2)      | 1069 |   62% [60-65] |   56% | 1.11 | 63/62 | RELIABLE |
| ema_trend                | 1217 |   60% [58-63] |   55% | 1.09 | 61/60 | significant |
| adx_di                   |  816 |   59% [56-63] |   55% | 1.08 | 60/58 | RELIABLE |
| rsi_momentum             |  860 |   62% [59-65] |   58% | 1.07 | 61/63 | significant |
| macd                     | 1211 |   59% [56-62] |   55% | 1.07 | 60/59 | significant |
| COMBO ema_trend+regime   |  492 |   61% [57-65] |   58% | 1.06 | 64/57 | — |
| regime                   |  536 |   60% [55-64] |   56% | 1.06 | 62/56 | — |
| COMBO regime+adx_di      |  536 |   60% [55-64] |   56% | 1.06 | 62/56 | — |
| COMBO adx_di+rsi_momentum |  654 |   61% [57-64] |   57% | 1.06 | 62/58 | stable |

### 1D (horizon 5 bars)

| signal | n | accuracy [95% CI] | base | lift | H1/H2 | verdict |
|---|---|---|---|---|---|---|
| COMBO ema_trend+regime   |  103 |   65% [55-74] |   54% | 1.20 | 57/72 | significant |
| COMBO adx_di+rsi_momentum |  138 |   63% [55-71] |   53% | 1.19 | 57/70 | RELIABLE |
| adx_di                   |  182 |   63% [55-69] |   53% | 1.19 | 55/72 | significant |
| COMBO all-agree          |   70 |   66% [54-76] |   56% | 1.18 | 68/64 | — |
| regime                   |  114 |   66% [57-74] |   56% | 1.17 | 60/71 | significant |
| COMBO regime+adx_di      |  114 |   66% [57-74] |   56% | 1.17 | 60/71 | significant |
| rsi_momentum             |  174 |   63% [56-70] |   55% | 1.16 | 60/66 | RELIABLE |
| COMBO majority(>=2)      |  221 |   62% [55-68] |   57% | 1.09 | 54/69 | — |
| ema_trend                |  249 |   60% [54-66] |   57% | 1.05 | 52/69 | — |
| bb_position              |  249 |   57% [51-63] |   57% | 0.99 | 47/68 | — |
| COMBO ema_trend+macd     |  191 |   59% [52-65] |   60% | 0.98 | 50/66 | — |
| macd                     |  244 |   53% [47-59] |   59% | 0.90 | 49/57 | — |

## ETH/USDT


### 1h (horizon 24 bars)

| signal | n | accuracy [95% CI] | base | lift | H1/H2 | verdict |
|---|---|---|---|---|---|---|
| COMBO ema_trend+regime   |  750 |   64% [61-67] |   51% | 1.27 | 65/63 | RELIABLE |
| regime                   |  871 |   63% [60-66] |   50% | 1.25 | 61/65 | RELIABLE |
| COMBO regime+adx_di      |  871 |   63% [60-66] |   50% | 1.25 | 61/65 | RELIABLE |
| COMBO all-agree          |  441 |   67% [62-71] |   55% | 1.21 | 67/66 | RELIABLE |
| adx_di                   | 1336 |   59% [56-62] |   50% | 1.18 | 60/58 | RELIABLE |
| COMBO adx_di+rsi_momentum |  991 |   59% [56-62] |   51% | 1.16 | 62/56 | significant |
| rsi_momentum             | 1349 |   56% [54-59] |   52% | 1.08 | 59/54 | significant |
| COMBO majority(>=2)      | 1774 |   55% [52-57] |   52% | 1.05 | 56/53 | significant |
| ema_trend                | 2058 |   54% [52-56] |   52% | 1.04 | 57/51 | — |
| bb_position              | 2058 |   53% [51-56] |   52% | 1.03 | 55/52 | — |
| COMBO ema_trend+macd     | 1520 |   53% [50-55] |   55% | 0.96 | 54/51 | — |
| macd                     | 2058 |   50% [48-52] |   52% | 0.96 | 49/51 | — |

### 4h (horizon 12 bars)

| signal | n | accuracy [95% CI] | base | lift | H1/H2 | verdict |
|---|---|---|---|---|---|---|
| COMBO adx_di+rsi_momentum |  598 |   67% [63-71] |   51% | 1.32 | 74/60 | RELIABLE |
| COMBO ema_trend+regime   |  464 |   69% [65-73] |   54% | 1.28 | 78/60 | RELIABLE |
| adx_di                   |  788 |   65% [62-68] |   51% | 1.28 | 68/62 | RELIABLE |
| COMBO majority(>=2)      | 1127 |   63% [61-66] |   50% | 1.26 | 66/61 | RELIABLE |
| COMBO all-agree          |  289 |   68% [63-73] |   54% | 1.25 | 81/56 | RELIABLE |
| rsi_momentum             |  889 |   63% [60-66] |   51% | 1.24 | 66/59 | RELIABLE |
| bb_position              | 1291 |   61% [59-64] |   51% | 1.21 | 63/59 | RELIABLE |
| ema_trend                | 1291 |   61% [58-64] |   51% | 1.21 | 65/57 | RELIABLE |
| COMBO ema_trend+macd     |  945 |   63% [60-66] |   52% | 1.20 | 66/60 | RELIABLE |
| regime                   |  521 |   66% [62-70] |   55% | 1.20 | 72/61 | RELIABLE |
| COMBO regime+adx_di      |  521 |   66% [62-70] |   55% | 1.20 | 72/61 | RELIABLE |
| macd                     | 1286 |   58% [55-61] |   51% | 1.14 | 59/57 | RELIABLE |

### 1D (horizon 5 bars)

| signal | n | accuracy [95% CI] | base | lift | H1/H2 | verdict |
|---|---|---|---|---|---|---|
| adx_di                   |  186 |   59% [51-65] |   53% | 1.11 | 52/66 | stable |
| ema_trend                |  246 |   58% [52-64] |   53% | 1.09 | 55/61 | stable |
| COMBO majority(>=2)      |  223 |   59% [52-65] |   54% | 1.08 | 53/64 | — |
| rsi_momentum             |  197 |   57% [50-64] |   53% | 1.08 | 53/62 | — |
| COMBO adx_di+rsi_momentum |  153 |   57% [49-64] |   53% | 1.07 | 55/59 | stable |
| bb_position              |  246 |   57% [51-63] |   53% | 1.07 | 54/60 | stable |
| regime                   |  132 |   58% [50-66] |   55% | 1.07 | 51/68 | — |
| COMBO regime+adx_di      |  132 |   58% [50-66] |   55% | 1.07 | 51/68 | — |
| COMBO ema_trend+regime   |  120 |   59% [50-68] |   57% | 1.04 | 55/65 | — |
| COMBO ema_trend+macd     |  178 |   56% [49-63] |   56% | 1.01 | 51/61 | — |
| COMBO all-agree          |   72 |   57% [45-68] |   58% | 0.98 | 55/60 | — |
| macd                     |  240 |   51% [45-57] |   54% | 0.95 | 46/55 | — |

---
**How to use:** rely on **RELIABLE** signals (significant edge that held in both halves); treat the rest as decoration. Note that even reliable directional edges here are small (lifts ~1.1-1.3) — consistent with the project finding that direction on liquid majors is near the predictability floor.
