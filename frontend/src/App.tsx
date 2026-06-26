import { useCallback, useEffect, useState } from "react";
import { fetchChart, fetchMicro, fetchCommentary, fetchSentiment, fetchScan, fetchOnchain, fetchAlerts, fetchAlertJournal, API_BASE } from "./api";
import type { AlertJournalResponse, AlertsResponse, ChartResponse, Commentary, MicroSnapshot, OnChain, ScanResponse, Sentiment } from "./types";
import { Controls } from "./components/Controls";
import { TrustBar } from "./components/TrustBar";
import { Section } from "./components/Section";
import { Dashboard } from "./components/Dashboard";
import { RegimeCard } from "./components/RegimeCard";
import { MicrostructureCard } from "./components/MicrostructureCard";
import { CommentaryCard } from "./components/CommentaryCard";
import { SentimentCard } from "./components/SentimentCard";
import { MarketScanCard } from "./components/MarketScanCard";
import { AlertsCard } from "./components/AlertsCard";
import { AlertJournalCard } from "./components/AlertJournalCard";
import { OnChainCard } from "./components/OnChainCard";
import { ErrorBoundary } from "./components/ErrorBoundary";

const SYMBOLS = ["BTC_USDT", "ETH_USDT"];
const TIMEFRAMES = ["1h", "4h", "1D"];

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
  const [auto, setAuto] = useState(false);
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [journal, setJournal] = useState<AlertJournalResponse | null>(null);
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

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchChart(symbol, timeframe),
      fetchMicro(symbol),
      fetchCommentary(symbol, timeframe),
      fetchSentiment(symbol),
      fetchOnchain(symbol),
    ])
      .then(([chart, m, n, s, oc]) => {
        setData(chart);
        setMicro(m);
        setNote(n);
        setSentiment(s);
        setOnchain(oc);
      })
      .catch((e: Error) => {
        setData(null);
        setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [symbol, timeframe]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadScan();
  }, [loadScan]);

  const pickInstrument = (inst: string) =>
    setSymbol(inst.endsWith("USDT") ? `${inst.slice(0, -4)}_USDT` : inst);

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
          symbols={Array.from(new Set([...SYMBOLS, symbol]))}
          timeframes={TIMEFRAMES}
          onSymbol={setSymbol}
          onTimeframe={setTimeframe}
          onRefresh={load}
          auto={auto}
          onAuto={setAuto}
        />
      </header>

      {/* ── The synthesized read, up top: everything condensed and analysed ── */}
      {data && <TrustBar data={data} timeframe={timeframe} />}

      {note && (
        <ErrorBoundary name="Analyst note">
          <CommentaryCard note={note} />
        </ErrorBoundary>
      )}

      {loading && <div className="status">Loading {symbol} {timeframe}…</div>}

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
        <Section title="Evidence" subtitle="regime · microstructure · sentiment · on-chain">
          <div className="cards-row">
            <ErrorBoundary name="Regime card">
              <RegimeCard regime={data.regime_current} timeframe={timeframe} />
            </ErrorBoundary>
            <ErrorBoundary name="Microstructure card">
              <MicrostructureCard micro={micro} />
            </ErrorBoundary>
          </div>
          <div className="cards-row">
            <ErrorBoundary name="Sentiment card">
              <SentimentCard sentiment={sentiment} />
            </ErrorBoundary>
            <ErrorBoundary name="On-chain card">
              <OnChainCard onchain={onchain} />
            </ErrorBoundary>
          </div>
        </Section>
      )}

      {!loading && !error && data && (
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
