interface Props {
  symbol: string;
  timeframe: string;
  symbols: string[];
  timeframes: string[];
  onSymbol: (s: string) => void;
  onTimeframe: (t: string) => void;
  onRefresh: () => void;
}

export function Controls({
  symbol, timeframe, symbols, timeframes, onSymbol, onTimeframe, onRefresh,
}: Props) {
  return (
    <div className="controls">
      <label htmlFor="symbol">Symbol</label>
      <select id="symbol" value={symbol} onChange={(e) => onSymbol(e.target.value)}>
        {symbols.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>

      <label htmlFor="tf">Timeframe</label>
      <select id="tf" value={timeframe} onChange={(e) => onTimeframe(e.target.value)}>
        {timeframes.map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>

      <button onClick={onRefresh} title="Reload from the analyst API">↻ Refresh</button>
    </div>
  );
}
