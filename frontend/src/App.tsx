import { useCallback, useEffect, useState } from "react";
import { fetchChart, API_BASE } from "./api";
import type { ChartResponse } from "./types";
import { Controls } from "./components/Controls";
import { TrustBar } from "./components/TrustBar";
import { Dashboard } from "./components/Dashboard";

const SYMBOLS = ["BTC_USDT", "ETH_USDT"];
const TIMEFRAMES = ["1h", "4h", "1D"];

export default function App() {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [timeframe, setTimeframe] = useState(TIMEFRAMES[0]);
  const [data, setData] = useState<ChartResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchChart(symbol, timeframe)
      .then((d) => setData(d))
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

      {loading && <div className="status">Loading {symbol} {timeframe}…</div>}

      {error && (
        <div className="status error">
          <p>Could not load data: {error}</p>
          <p className="footnote">
            Is the analyst API running at <code>{API_BASE}</code>? Start it with{" "}
            <code>uvicorn analyst.api.app:app</code>, and make sure data is ingested for this
            symbol/timeframe.
          </p>
        </div>
      )}

      {!loading && !error && data && <Dashboard data={data} />}

      <p className="footnote">
        All indicators are computed by the Python engine (single source of truth) and verified
        against TA-Lib; the browser never recomputes technical analysis.
      </p>
    </div>
  );
}
