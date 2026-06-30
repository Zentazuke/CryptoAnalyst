import { useCallback, useEffect, useRef, useState } from "react";
import { fetchChart, fetchMicro, fetchCommentary, fetchSentiment, fetchScan, fetchOnchain, fetchAlerts, fetchAlertJournal, fetchDataHealth, fetchVrp, fetchVrpJournal, API_BASE } from "./api";
import type { AlertJournalResponse, AlertsResponse, ChartResponse, Commentary, DataHealth, MicroSnapshot, OnChain, ScanResponse, Sentiment, VrpRead, VrpJournalResponse } from "./types";
import { DataHealthBar } from "./components/DataHealthBar";
import { VrpCard } from "./components/VrpCard";
import { Controls } from "./components/Controls";
import { TrustBar } from "./components/TrustBar";
import { Section } from "./components/Section";
import { Dashboard } from "./components/Dashboard";
import { RegimeCard } from "./components/RegimeCard";
import { MicrostructureCard } from "./components/MicrostructureCard";
import { CommentaryCard } from "./components/CommentaryCard";
import { MetricBreakdown } from "./components/MetricBreakdown";
import { EnsembleCard } from "./components/EnsembleCard";
import { SentimentCard } from "./components/SentimentCard";
import { MarketScanCard } from "./components/MarketScanCard";
import { AlertsCard } from "./components/AlertsCard";
import { AlertJournalCard } from "./components/AlertJournalCard";
import { OnChainCard } from "./components/OnChainCard";
import { ErrorBoundary } from "./components/ErrorBoundary";

const SYMBOLS = ["BTC_USDT", "ETH_USDT", "ROBO_USDC"];
const TIMEFRAMES = ["1h", "4h", "1D"];

/** Exchange instrument ("BTCUSDT") -> internal symbol ("BTC_USDT"). */
const toInternal = (inst: string) =>
  inst.endsWith("USDT") ? `${inst.slice(0, -4)}_USDT` : inst;

// Binance gives no market cap, so we order the picker the way every market site
// does: by market-cap rank (stables excluded — the scanner drops them too).
// Coins outside this list fall in afterwards, in the scan's (volume) order.
const MCAP_ORDER = [
  "BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "TRX", "AVAX", "LINK",
  "TON", "SHIB", "DOT", "BCH", "NEAR", "LTC", "POL", "MATIC", "UNI", "ICP",
  "APT", "XLM", "ETC", "FIL", "HBAR", "ARB", "OP", "ATOM", "INJ", "SUI",
];
const mcapRank = (internalSymbol: string) => {
  const i = MCAP_ORDER.indexOf(internalSymbol.replace("_USDT", ""));
  return i === -1 ? Number.MAX_SAFE_INTEGER : i;
};

export default function App() {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [timeframe, setTimeframe] = useState(TIMEFRAMES[0]);
  const [data, setData] = useState<ChartResponse | null>(null);
  const [micro, setMicro] = useState<MicroSnapshot | null>(null);
  const [note, setNote] = useState<Commentary | null>(null);
  const [sentiment, setSentiment] = useState<Sentiment | null>(null);
  const [onchain, setOnchain] = useState<OnChain | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [noteLoading, setNoteLoading] = useState(false);
  const [auto, setAuto] = useState(false);
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [journal, setJournal] = useState<AlertJournalResponse | null>(null);
  const [health, setHealth] = useState<DataHealth | null>(null);
  const [vrp, setVrp] = useState<VrpRead | null>(null);
  const [vrpJournal, setVrpJournal] = useState<VrpJournalResponse | null>(null);
  const [scanLoading, setScanLoading] = useState(false);

  const loadScan = useCallback(() => {
    setScanLoading(true);
    Promise.all([fetchScan("4h", 24), fetchAlerts("4h", 24), fetchAlertJournal(40)])
      .then(([sc, al, jr]) => {
        setScan(sc);
        setAlerts(al);
        setJournal(jr);
      })
      .finally(() => setScanLoading(false));
  }, []);

  // Live feeds — charts, microstructure and sentiment. Driven by the symbol/
  // timeframe pickers, the Refresh button, and the Live auto-poll.
  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchChart(symbol, timeframe),
      fetchMicro(symbol),
      fetchSentiment(symbol),
    ])
      .then(([chart, m, s]) => {
        setData(chart);
        setMicro(m);
        setSentiment(s);
      })
      .catch((e: Error) => {
        setData(null);
        setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [symbol, timeframe]);

  // Analyst commentary is decoupled from the live feeds: it only regenerates
  // when you press Simulate. Each run pulls a fresh read from the latest live
  // data (the backend always serves current candles).
  const simulate = useCallback(() => {
    setNoteLoading(true);
    fetchCommentary(symbol, timeframe)
      .then(setNote)
      .finally(() => setNoteLoading(false));
  }, [symbol, timeframe]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadScan();
  }, [loadScan]);

  // On-chain is slow-moving daily data — load once per symbol, never polled.
  useEffect(() => {
    fetchOnchain(symbol).then(setOnchain).catch(() => setOnchain(null));
  }, [symbol]);

  // VRP read (BTC/ETH only) — slow-moving, load per symbol; null hides the card.
  useEffect(() => {
    setVrp(null);
    fetchVrp(symbol).then(setVrp).catch(() => setVrp(null));
    fetchVrpJournal().then(setVrpJournal).catch(() => setVrpJournal(null));
  }, [symbol]);

  // Data-health: poll independently so liveness is always current (every 20s).
  useEffect(() => {
    const tick = () => fetchDataHealth().then(setHealth).catch(() => {});
    tick();
    const id = setInterval(tick, 20000);
    return () => clearInterval(id);
  }, []);

  // Drop the stale note when the instrument/timeframe changes so the card never
  // shows a read that no longer matches what you're looking at.
  useEffect(() => {
    setNote(null);
  }, [symbol, timeframe]);

  // Generate one initial read on first mount so the card isn't empty.
  const didInit = useRef(false);
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    simulate();
  }, [simulate]);

  const pickInstrument = (inst: string) => setSymbol(toInternal(inst));

  // Top coins sourced live from the market scan, ordered by market-cap rank
  // (stable, like other market sites). Falls back to the static defaults until
  // the scan lands, and always includes the active symbol.
  const symbolOptions = Array.from(
    new Set([
      ...(scan?.rows ?? []).map((r) => toInternal(r.instrument)),
      ...SYMBOLS,
      symbol,
    ]),
  ).sort((a, b) => mcapRank(a) - mcapRank(b));

  // real-time feel: poll while auto-refresh is on
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [auto, load]);

  return (
    <div className="app">
      <header className="app-head">
        <h1>
          Crypto Analyst <span className="dim">· technical visualizer</span>
        </h1>
        <Controls
          symbol={symbol}
          timeframe={timeframe}
          symbols={symbolOptions}
          timeframes={TIMEFRAMES}
          onSymbol={setSymbol}
          onTimeframe={setTimeframe}
          onRefresh={load}
          auto={auto}
          onAuto={setAuto}
        />
      </header>

      <DataHealthBar health={health} />

      {/* ── The synthesized read, up top: everything condensed and analysed ── */}
      {data && <TrustBar data={data} timeframe={timeframe} />}

      {/* The one validated edge: the volatility-risk-premium cockpit (BTC/ETH). */}
      <ErrorBoundary name="VRP">
        <VrpCard vrp={vrp} journal={vrpJournal} />
      </ErrorBoundary>

      <ErrorBoundary name="Analyst note">
        <CommentaryCard
          note={note}
          symbol={symbol}
          timeframe={timeframe}
          loading={noteLoading}
          onSimulate={simulate}
        />
      </ErrorBoundary>

      {note?.ensemble && (
        <ErrorBoundary name="Ensemble">
          <EnsembleCard ens={note.ensemble} timeframe={timeframe} />
        </ErrorBoundary>
      )}

      {note?.metric_reads && note.metric_reads.length > 0 && (
        <Section title="Analyst breakdown" subtitle="each metric read on its own — what it shows, means & where it points">
          <ErrorBoundary name="Metric breakdown">
            <MetricBreakdown reads={note.metric_reads} />
          </ErrorBoundary>
        </Section>
      )}

      {loading && !data && <div className="status">Loading {symbol} {timeframe}…</div>}

      {error && (
        <div className="status error">
          <p>Could not load data: {error}</p>
          <p className="footnote">
            The page calls <code>{API_BASE}</code>, proxied to the analyst API on port 8000.
            Easiest fix: close everything and run <code>run-analyst.bat</code> — it starts the API +
            visualizer and ingests data for you.
          </p>
        </div>
      )}

      {/* ── Then we break it apart: the evidence behind the read ── */}
      {data && (
        <Section title="Evidence" subtitle="regime · microstructure · on-chain · sentiment">
          <div className="cards-row">
            <ErrorBoundary name="Regime card">
              <RegimeCard regime={data.regime_current} timeframe={timeframe} />
            </ErrorBoundary>
            <ErrorBoundary name="Microstructure card">
              <MicrostructureCard micro={micro} />
            </ErrorBoundary>
          </div>
          <div className="cards-row">
            <ErrorBoundary name="On-chain card">
              <OnChainCard onchain={onchain} />
            </ErrorBoundary>
          </div>
          {/* Sentiment carries the most content — give it the full width so it
              has room to breathe instead of overflowing a half-column. */}
          <ErrorBoundary name="Sentiment card">
            <SentimentCard sentiment={sentiment} />
          </ErrorBoundary>
        </Section>
      )}

      {data && (
        <Section title="Charts" subtitle="price, levels & indicator panes">
          <ErrorBoundary name="Charts">
            <Dashboard data={data} />
          </ErrorBoundary>
        </Section>
      )}

      <Section title="Market scan & alerts" subtitle="breadth, live setups & fired-alert track record">
        <ErrorBoundary name="Market scan">
          <MarketScanCard
            scan={scan}
            loading={scanLoading}
            onRefresh={loadScan}
            onPick={pickInstrument}
          />
        </ErrorBoundary>
        <div className="cards-row">
          <ErrorBoundary name="Alerts">
            <AlertsCard data={alerts} onPick={pickInstrument} />
          </ErrorBoundary>
          <ErrorBoundary name="Alert journal">
            <AlertJournalCard data={journal} onPick={pickInstrument} />
          </ErrorBoundary>
        </div>
      </Section>

      <p className="footnote">
        All indicators and the regime call are computed by the Python engine (single source of
        truth), verified against TA-Lib, and causal (no look-ahead). Regime reliability shown is
        measured by walk-forward calibration — not asserted.
      </p>
    </div>
  );
}
