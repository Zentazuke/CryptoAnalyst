import { useCallback, useEffect, useState } from "react";
import { fetchChart, fetchMicro, fetchCommentary, API_BASE } from "./api";
import type { ChartResponse, Commentary, MicroSnapshot } from "./types";
import { Controls } from "./components/Controls";
import { TrustBar } from "./components/TrustBar";
import { Dashboard } from "./components/Dashboard";
import { RegimeCard } from "./components/RegimeCard";
import { MicrostructureCard } from "./components/MicrostructureCard";
import { CommentaryCard } from "./components/CommentaryCard";

const SYMBOLS = ["BTC_USDT", "ETH_USDT"];
const TIMEFRAMES = ["1h", "4h", "1D"];

export default function App() {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [timeframe, setTimeframe] = useState(TIMEFRAMES[0]);
  const [data, setData] = useState<ChartResponse | null>(null);
  const [micro, setMicro] = useState<MicroSnapshot | null>(null);
  const [note, setNote] = useState<Commentary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([fetchChart(symbol, timeframe), fetchMicro(symbol), fetchCommentary(symbol, timeframe)])
      .then(([chart, m, n]) => {
        setData(chart);
        setMicro(m);
        setNote(n);
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

  return (
    <div className="app">
      <header className="app-head">
        <h1>
          Crypto Analyst <span className="dim">· technical visualizer</span>
        </h1>
        <Controls
          symbol={symbol}
          timeframe={timeframe}
          symbols={SYMBOLS}
          timeframes={TIMEFRAMES}
          onSymbol={setSymbol}
          onTimeframe={setTimeframe}
          onRefresh={load}
        />
      </header>

      {data && <TrustBar data={data} timeframe={timeframe} />}

      {note && <CommentaryCard note={note} />}

      {data && (
        <div className="cards-row">
          <RegimeCard regime={data.regime_current} timeframe={timeframe} />
          <MicrostructureCard micro={micro} />
        </div>
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

      {!loading && !error && data && <Dashboard data={data} />}

      <p className="footnote">
        All indicators and the regime call are computed by the Python engine (single source of
        truth), verified against TA-Lib, and causal (no look-ahead). Regime reliability shown is
        measured by walk-forward calibration — not asserted.
      </p>
    </div>
  );
}
