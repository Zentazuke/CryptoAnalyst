# Crypto Analyst

A standalone, **verifiable** crypto analytics tool. We build the analyst first;
the grid bot only comes after the analyst is a workable, trusted instrument.

Design principle: **trust is a subsystem, not an afterthought.** Every datapoint
carries its source and ingest time; raw payloads are archived for replay; and
data-quality checks (starting with gap detection) gate what we believe.

## Phase A0 — Foundation (this milestone)

Ingest live OHLCV from the Crypto.com public REST API, persist to DuckDB with
provenance, archive raw payloads, and detect gaps.

### Setup

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -e .
```

### Ingest data

```powershell
.venv\Scripts\python.exe -m analyst.ingest --symbols BTC_USDT,ETH_USDT --timeframe 1h --count 300
```

### Serve the read API

```powershell
.venv\Scripts\python.exe -m uvicorn analyst.api.app:app --reload
```

- `GET /health` — store reachability + per-symbol freshness
- `GET /provenance/{symbol}` — where each series came from + when ingested
- `GET /candles/{symbol}?timeframe=1h&limit=200`
- `GET /quality/{symbol}` — recent data-quality results
- `GET /indicators/{symbol}?timeframe=1h` — latest TA snapshot (A1)

### Test

```powershell
.venv\Scripts\python.exe -m pytest
```

## Layout

```
analyst/
  config/      settings (paths, API base, timeframe table)
  ingestion/   data-source contract, Crypto.com source, raw archival
  storage/     DuckDB store (ohlcv + ingest_log + data_quality)
  quality/     gap detection (the first trust check)
  api/         FastAPI read endpoints
  ingest.py    orchestrator + CLI
tests/         parity / no-lookahead / quality tests
data/          duckdb file + raw/ archive (gitignored)
```

## Roadmap

- [x] **A0 Foundation** — ingestion, DuckDB store, provenance, gap detection
- [x] **A1 TA engine** — ATR/EMA/SMA/RSI/MACD/Bollinger/VWAP/ADX/realized-vol,
  causal (no look-ahead), verified against TA-Lib + golden vectors + invariants
- [ ] A2 Microstructure (spread, depth, OI, funding, basis)
- [ ] A3 Regime classifier + calibration
- [ ] A4 Dashboards + alerts
- [ ] A5 On-chain · A6 Sentiment/options · A7 Research workbench

### Indicator conventions

EMA is SMA-seeded; RSI/ATR/ADX use Wilder smoothing; Bollinger uses population
std — all matching the TA-Lib reference. Every indicator is **causal**: the
value at bar *i* uses only data up to bar *i*, enforced by the no-look-ahead
test suite.
