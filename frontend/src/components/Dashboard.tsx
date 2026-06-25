import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  LineStyle,
  type UTCTimestamp,
  type IChartApi,
} from "lightweight-charts";
import type { ChartResponse, LinePoint } from "../types";

const ts = (t: number) => t as UTCTimestamp;
const toLine = (pts: LinePoint[]) => pts.map((p) => ({ time: ts(p.time), value: p.value }));

const baseOptions = {
  layout: { background: { type: ColorType.Solid, color: "#131823" }, textColor: "#c9d1d9" },
  grid: { vertLines: { color: "#1b2230" }, horzLines: { color: "#1b2230" } },
  rightPriceScale: { borderColor: "#1b2230" },
  timeScale: { borderColor: "#1b2230", timeVisible: true, secondsVisible: false },
  crosshair: { mode: CrosshairMode.Normal },
  autoSize: true,
};

export function Dashboard({ data }: { data: ChartResponse }) {
  const priceRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!priceRef.current || !rsiRef.current || !macdRef.current) return;

    const priceChart = createChart(priceRef.current, { ...baseOptions, height: 380 });
    const rsiChart = createChart(rsiRef.current, { ...baseOptions, height: 150 });
    const macdChart = createChart(macdRef.current, { ...baseOptions, height: 170 });

    // --- price: candles + volume + Bollinger + MAs ---
    const candles = priceChart.addCandlestickSeries({
      upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
      wickUpColor: "#26a69a", wickDownColor: "#ef5350",
    });
    candles.setData(
      data.candles.map((c) => ({
        time: ts(c.time), open: c.open, high: c.high, low: c.low, close: c.close,
      })),
    );

    const volume = priceChart.addHistogramSeries({
      priceFormat: { type: "volume" }, priceScaleId: "vol",
    });
    priceChart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volume.setData(data.volume.map((v) => ({ time: ts(v.time), value: v.value, color: "#2b3340" })));

    const overlay = (key: string, color: string, width: 1 | 2 = 1) => {
      const pts = data.overlays[key];
      if (!pts?.length) return;
      const s = priceChart.addLineSeries({
        color, lineWidth: width, priceLineVisible: false, lastValueVisible: false,
      });
      s.setData(toLine(pts));
    };
    overlay("bb_upper", "#4b5a78");
    overlay("bb_lower", "#4b5a78");
    overlay("bb_mid", "#8892b0");
    overlay("sma_20", "#58a6ff", 2);
    overlay("ema_20", "#e3b341", 2);

    // --- RSI panel with 70/30 guides ---
    const rsi = rsiChart.addLineSeries({ color: "#d29922", lineWidth: 2, priceLineVisible: false });
    rsi.setData(toLine(data.panels.rsi_14 ?? []));
    for (const [price, color] of [[70, "#ef5350"], [30, "#26a69a"]] as const) {
      rsi.createPriceLine({
        price, color, lineStyle: LineStyle.Dashed, lineWidth: 1,
        axisLabelVisible: true, title: String(price),
      });
    }

    // --- MACD panel: histogram + macd + signal ---
    const hist = macdChart.addHistogramSeries({ priceLineVisible: false });
    hist.setData(
      (data.panels.macd_hist ?? []).map((p) => ({
        time: ts(p.time), value: p.value, color: p.value >= 0 ? "#26a69a" : "#ef5350",
      })),
    );
    const macdLine = macdChart.addLineSeries({ color: "#58a6ff", lineWidth: 2, priceLineVisible: false });
    macdLine.setData(toLine(data.panels.macd ?? []));
    const signal = macdChart.addLineSeries({ color: "#e3b341", lineWidth: 1, priceLineVisible: false });
    signal.setData(toLine(data.panels.macd_signal ?? []));

    // --- sync time scales across the three panes ---
    const charts: IChartApi[] = [priceChart, rsiChart, macdChart];
    let syncing = false;
    const unsub = charts.map((chart, i) => {
      const handler = (range: unknown) => {
        if (syncing || !range) return;
        syncing = true;
        charts.forEach((other, j) => {
          if (i !== j) other.timeScale().setVisibleLogicalRange(range as never);
        });
        syncing = false;
      };
      chart.timeScale().subscribeVisibleLogicalRangeChange(handler);
      return () => chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler);
    });

    priceChart.timeScale().fitContent();

    return () => {
      unsub.forEach((fn) => fn());
      charts.forEach((c) => c.remove());
    };
  }, [data]);

  return (
    <>
      <div className="chart-card">
        <div className="title">
          <span>{data.symbol} · {data.timeframe} · price</span>
          <span className="legend-key"><span className="legend-swatch" style={{ background: "#58a6ff" }} />SMA 20</span>
          <span className="legend-key"><span className="legend-swatch" style={{ background: "#e3b341" }} />EMA 20</span>
          <span className="legend-key"><span className="legend-swatch" style={{ background: "#8892b0" }} />Bollinger 20·2</span>
        </div>
        <div ref={priceRef} />
      </div>

      <div className="chart-card">
        <div className="title"><span>RSI 14</span></div>
        <div ref={rsiRef} />
      </div>

      <div className="chart-card">
        <div className="title">
          <span>MACD 12·26·9</span>
          <span className="legend-key"><span className="legend-swatch" style={{ background: "#58a6ff" }} />MACD</span>
          <span className="legend-key"><span className="legend-swatch" style={{ background: "#e3b341" }} />Signal</span>
        </div>
        <div ref={macdRef} />
      </div>
    </>
  );
}
