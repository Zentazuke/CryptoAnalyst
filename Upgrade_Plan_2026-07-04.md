# Crypto-Analyst — Upgrade Plan (2026-07-04)
*Response to the external evaluation ("research cockpit, not yet analyst terminal"). Verified against the repo before planning. The plan keeps the project's core rule: **no metric ships until it's calibrated; no feature ships without evidence it helps.***

---

## 0. Fact-check of the evaluation (verified today)

- **4h lean CSV "broken":** confirmed all 21,500 rows are `lean=neutral, score=0` — but this is *by design*, not a bug: `export_lean.py --no-ensemble` exports regime labels only (the ensemble is too slow at 4h). The evaluator's warning still stands operationally: the file *looks* like it contains a lean signal. → P0 fix: stop emitting fake-looking columns.
- **`.env` in the zip:** the repo is clean (`.env` untracked, `.gitignore` covers `.env`, `.venv`, DuckDB, raw data). The leak was the hand-made zip of the whole folder. → P0 fix: a release script so a human never builds the archive by hand again. Rotate the testnet keys regardless.
- **Scores:** broadly fair. One pushback: "on-chain 4/10, too thin" is true, but the fix is NOT ingesting 20 metrics — every past attempt to use uncalibrated breadth died in the graveyard. Breadth follows calibration, never precedes it.

---

## P0 — Hygiene (days, do first)

1. **Rotate the Binance testnet keys** (they were in a shared zip; testnet or not, rotate).
2. **`scripts/make_release.py`** — builds a clean zip from an explicit whitelist (`analyst/`, `frontend/src/`, `tests/`, `scripts/`, `README.md`, `pyproject.toml`, `package.json`, `package-lock.json`, `.env.example`) and *refuses to run* if the staging tree contains `.env`, `.venv`, `node_modules`, `*.duckdb`, `data/raw`, `.pytest_cache`, `dist`. Packaging becomes impossible to get wrong.
3. **Fix the 4h export shape:** `--no-ensemble` writes `lean=,score=,normalized=` (empty) instead of `neutral/0`, and names the file `analyst_regime_4h.csv`. Update the Trading Bot consumers to read only `regime,confidence` from it. A file must not look like it contains a signal it doesn't.
4. **`.env.example`** covering every env var the app reads, with comments.

## P1 — The trust core (1–2 weeks; this is the moat)

The evaluator's best point: sentiment and on-chain are "fetched live, unproven." The differentiator of this app is calibration — extend it to every layer:

1. **Persist everything scored.** New DuckDB tables `sentiment_history` and `onchain_history` (metric, symbol, ts, value, source, ingest_ts — same provenance pattern as candles). The scheduler snapshots them on every run. Without history there is no calibration; without calibration a metric is decoration.
2. **One calibration harness for all metrics.** Generalize `signal_eval` so ANY stored series can be tested the SIGNAL_CARD way (direction accuracy vs base rate, 95% CI, H1/H2 stability, on vol-scaled significant moves). Auto-regenerate SIGNAL_CARD.md to include sentiment/on-chain rows.
3. **Gate the UI on the card.** A metric renders in commentary/composite ONLY with verdict ≥ *significant*; RELIABLE gets full weight. Everything else appears (if at all) in a clearly-labeled "unproven" drawer. This is the enforcement mechanism that keeps the app honest as it grows.
4. **`GET /explain/{symbol}`** — the evaluator's "explainability" item, and the data already exists: return every currently-fired signal with its hit rate, n, base rate, CI, and verdict. Frontend: click any read → evidence panel. This single endpoint converts the cockpit into an *auditable* analyst.

## P2 — Data layer, triaged (2–4 weeks, in this order)

Rule: each addition = ingest → persist → calibrate → card → only then UI. Anything that fails calibration goes to the graveyard *documented*, same as strategies.

**Tier 1 (free sources already integrated, likely value):**
- **Options skew + term structure** (Deribit public API, already used for DVOL): 25Δ risk-reversal, ATM term slope. Crowding/fear reads that complement VRP.
- **Liquidations + taker-flow CVD** (Binance public): the "flash risk" regime's natural confirmer; also candidate pump-confirmation refinement.
- **Stablecoin supply/flows** (DefiLlama, free — the Trading Bot already fetches this): port into the analyst, persist, calibrate as the risk-off input it already informally is.

**Tier 2 (free but weaker priors):**
- **TVL / fees / protocol revenue / DEX volume** (DefiLlama): fundamental context per coin; calibrate at weekly horizon.
- **BTC dominance / sector relative strength** (computable from existing OHLCV — no new source).
- **Exchange netflows / MVRV / SOPR**: only what Coin Metrics community tier actually exposes; do NOT buy data yet. If free coverage is too thin, note it in the model card and move on.

**Explicitly deferred (documented, not forgotten):** whale wallets, token unlocks, KOL/narrative tracking, L2 activity, DeFi pool risk. High noise, costly data, no calibration path today. Revisit only when P1's harness can score them.

## P3 — Product: cockpit → terminal (in parallel with P2, frontend-weighted)

1. **Watchlists** — user-defined lists (Majors / Solana eco / high-funding / new-breakouts), stored locally (DuckDB table), scanner and alerts become watchlist-aware. Cheap, high daily-use value.
2. **Metric explorer** — one generic `GET /series/{metric}?symbols=...` endpoint over the persisted stores + one chart view with multi-symbol compare. Kills the "prebuilt cards only" limitation with a single generic path.
3. **Composite "analyst state"** — per symbol: technical / derivatives / on-chain / sentiment / risk sub-scores → one state, where **weights come from calibration (lift × reliability), not hand-tuning**, uncalibrated metrics contribute 0, and every score links to /explain. The evaluator's "multi-layer decision engine," built the only defensible way.
4. **Portfolio/risk mode** — input: current positions (read `tsm_live.db` + manual entries). Output: correlation matrix (stored candles), parametric VaR + a "BTC −7%" beta-stress, per-regime historical P&L of the basket ("what regimes hurt this portfolio" — the regime labels already exist). No optimizer, no fake precision — exposure awareness.

## P4 — Engineering (ongoing, start with CI this week)

1. **CI (GitHub Actions):** pytest (Linux deps installed fresh — this also catches the "works only with my Windows .venv" class of failure the evaluator hit), `tsc --noEmit`, `vite build`, uvicorn boot + `/health` smoke. Every commit.
2. **Docker:** backend Dockerfile + compose (API + frontend build); eliminates platform-specific breakage (the Rollup/node_modules issue was exactly this).
3. **Auth:** optional bearer token on the API (same pattern as the dashboard's close-header), required when bound to non-localhost.
4. **Path/config audit:** no hardcoded Windows paths; all config via env with sane defaults; structured logs with rotation.

---

## Sequencing & acceptance

| Phase | Time | Done when | Status |
|---|---|---|---|
| P0 | days | keys rotated; release script refuses dirty zips; 4h file can't be misread | ✅ 2026-07-04 (keys: Ricardo) |
| P1 | 1–2 wk | sentiment/on-chain persisted; SIGNAL_CARD covers them; /explain live | 🟡 P1.1 + P1.2 + P1.4 done 2026-07-04; P1.3 (UI gating) next |
| P2 T1 | 2–4 wk | skew, liquidations/CVD, stablecoins persisted + carded (pass or graveyard) | 🟡 feeds shipped 2026-07-04 (`p2_feeds` task); carding waits on accrued history |
| P3 | parallel | watchlists + explorer shipped; composite only over calibrated signals | 🟡 watchlists backend done 2026-07-04; explorer UI + composite next |
| P4 | ongoing | CI green on Linux; docker-compose up works on a clean machine | 🟡 CI green ✅; bearer-token auth done 2026-07-04; Docker next session |

**Also done 2026-07-04 (second pass):** P4.3 optional bearer auth (`ANALYST_API_TOKEN` env; /health exempt; off by default — set it if the API ever binds beyond localhost) and P3.1 watchlists (own DuckDB store + GET/POST/DELETE `/watchlists` endpoints; CORS widened to POST/DELETE). Both tested; suite at 187 green, 32 routes.

**Done 2026-07-07:** P1.3 `EvidencePanel.tsx` (every fired signal with receipts — reliable rows prominent, significant-but-unstable dimmed, uncalibrated behind a "decoration" drawer) + P3.2 `MetricExplorer.tsx` (catalog + dependency-free SVG chart over every persisted series incl. GLOBAL stableflow, labeled UNCALIBRATED until carded) + api.ts fetchers, wired into App. Verified: clean `npm ci` + `tsc` + `vite build` green.

**REMAINING:** P4.2 Dockerfile/compose (next build item); P3 composite score + metric carding **data-gated** until ~4–6 weeks of scheduler history exists (~early-mid August 2026); P2 Tier-2 sources after Tier-1 verdicts.

**Done 2026-07-04** (all verified against the full test suite on clean Linux — 173 tests passing):
- P0.2 `scripts/make_release.py` · P0.3 4h export fix · P0.4 `.env.example` · P4.1 CI workflow
- P1.4 `analyst/explain.py` + `GET /explain/{symbol}` (+5 tests) — every fired signal with its receipts
- P1.1 `analyst/storage/history.py` (MetricHistory, long-format DuckDB) + scheduler `metric_history` task (sentiment 15-min gap, on-chain 6-h gap) + `GET /metric-history/{symbol}` (+5 tests). **History starts accruing as soon as the API runs with `ANALYST_SCHEDULER=1` — start it soon; calibration needs weeks of data.**
- P2 T1 `analyst/p2_feeds.py` + scheduler `p2_feeds` task (+6 tests): Deribit options surface (near/far ATM IV, term slope, ±10%-moneyness risk-reversal skew proxy — one call, consistency-over-convention), Binance futures crowd (taker buy/sell ratio, top-trader L/S, OI + 1h change; NOTE: liquidation *events* need a websocket — deferred, the crowd ratios are the REST-able proxy), DefiLlama stablecoin supply (USDT/USDC/total, layer `stableflow`, symbol GLOBAL). All fetchers injectable-HTTP, fail-open per part. History accrues under layers `options` / `derivatives` / `stableflow`; the P1.2 harness cards them when the data matures.
- P1.2 `analyst/metric_calibration.py` + `GET /metric-calibration/{symbol}` (+6 tests): any stored series → SIGNAL_CARD-grade verdict. Fixed a-priori signal convention (value vs trailing-60-obs median), BOTH orientations scored with the both-halves stability rule absorbing the doubled luck surface, staleness guard from the series' own cadence, `best_row()` = reliable-or-nothing. Validated on planted-edge / inverted / noise worlds. **Becomes decisive once P1.1 history matures — it runs today on whatever exists.**

**What we deliberately do NOT do:** add indicators for breadth, buy data before free sources are exhausted, hand-tune composite weights, or ship any signal the calibration harness hasn't scored. The evaluator is right that the next breakthrough is the multi-layer decision engine — but the reason this app is credible is that every layer it has is *proven*. Growth must not break that.
