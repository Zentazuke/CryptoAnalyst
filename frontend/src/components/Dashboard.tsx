import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  LineStyle,
  type UTCTimestamp,
  type IChartApi,
} from "lightweight-charts";
import type { ChartResponse, LinePoint } from "../types";
import { regimeColor } from "../regime";

const ts = (t: number) => t as UTCTimestamp;
const toLine = (pts: LinePoint[] = []) => pts.map((p) => ({ time: ts(p.time), value: p.value }));

const baseOptions = {
  layout: { background: { type: ColorType.Solid, color: "#131823" }, textColor: "#c9d1d9" },
  grid: { vertLines: { color: "#1b2230" }, horzLines: { color: "#1b2230" } },
  rightPriceScale: { borderColor: "#1b2230", minimumWidth: 64 }, // equal width keeps panes aligned
  timeScale: { borderColor: "#1b2230", timeVisible: true, secondsVisible: false },
  crosshair: { mode: CrosshairMode.Normal },
  autoSize: true,
};

export function Dashboard({ data }: { data: ChartResponse }) {
  const priceRef = useRef<HTMLDivElement>(null);
  const regimeRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const adxRef = useRef<HTMLDivElement>(null);
  const fundingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const refs = [priceRef, regimeRef, rsiRef, macdRef, adxRef, fundingRef];
    if (refs.some((r) => !r.current)) return;

    const charts: IChartApi[] = [];
    try {
    const price = createChart(priceRef.current!, { ...baseOptions, height: 340 });
    const regime = createChart(regimeRef.current!, { ...baseOptions, height: 56 });
    const rsi = createChart(rsiRef.current!, { ...baseOptions, height: 130 });
    const macd = createChart(macdRef.current!, { ...baseOptions, height: 140 });
    const adx = createChart(adxRef.current!, { ...baseOptions, height: 140 });
    const funding = createChart(fundingRef.current!, { ...baseOptions, height: 120 });
    charts.push(price, regime, rsi, macd, adx, funding);

    // --- price: candles + volume + Bollinger + MAs ---
    const candles = price.addCandlestickSeries({
      upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
      wickUpColor: "#26a69a", wickDownColor: "#ef5350",
    });
    candles.setData(
      data.candles.map((c) => ({ time: ts(c.time), open: c.open, high: c.high, low: c.low, close: c.close })),
    );
    const volume = price.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol" });
    price.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volume.setData(data.volume.map((v) => ({ time: ts(v.time), value: v.value, color: "#2b3340" })));

    const overlay = (key: string, color: string, width: 1 | 2 = 1) => {
      const pts = data.overlays[key];
      if (!pts?.length) return;
      const s = price.addLineSeries({ color, lineWidth: width, priceLineVisible: false, lastValueVisible: false });
      s.setData(toLine(pts));
    };
    overlay("bb_upper", "#4b5a78");
    overlay("bb_lower", "#4b5a78");
    overlay("bb_mid", "#8892b0");
    overlay("sma_20", "#58a6ff", 2);
    overlay("ema_20", "#e3b341", 2);

    // --- regime ribbon: one colored bar per candle ---
    const ribbon = regime.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
    ribbon.setData(
      data.regime.map((r) => ({ time: ts(r.time), value: 1, color: regimeColor(r.label) })),
    );
    regime.priceScale("right").applyOptions({ scaleMargins: { top: 0.1, bottom: 0 } });

    // --- RSI with 70/30 guides ---
    const rsiLine = rsi.addLineSeries({ color: "#d29922", lineWidth: 2, priceLineVisible: false });
    rsiLine.setData(toLine(data.panels.rsi_14));
    for (const [p, col] of [[70, "#ef5350"], [30, "#26a69a"]] as const) {
      rsiLine.createPriceLine({ price: p, color: col, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: String(p) });
    }

    // --- MACD: histogram + macd + signal ---
    const hist = macd.addHistogramSeries({ priceLineVisible: false });
    hist.setData((data.panels.macd_hist ?? []).map((p) => ({
      time: ts(p.time), value: p.value, color: p.value >= 0 ? "#26a69a" : "#ef5350",
    })));
    macd.addLineSeries({ color: "#58a6ff", lineWidth: 2, priceLineVisible: false }).setData(toLine(data.panels.macd));
    macd.addLineSeries({ color: "#e3b341", lineWidth: 1, priceLineVisible: false }).setData(toLine(data.panels.macd_signal));

    // --- ADX + directional indicators, with the 25 "trending" guide ---
    const adxLine = adx.addLineSeries({ color: "#c9d1d9", lineWidth: 2, priceLineVisible: false });
    adxLine.setData(toLine(data.panels.adx_14));
    adxLine.createPriceLine({ price: 25, color: "#8892b0", lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "25" });
    adx.addLineSeries({ color: "#26a69a", lineWidth: 1, priceLineVisible: false }).setData(toLine(data.panels.plus_di));
    adx.addLineSeries({ color: "#ef5350", lineWidth: 1, priceLineVisible: false }).setData(toLine(data.panels.minus_di));

    // --- funding: signed histogram around zero ---
    const fund = funding.addHistogramSeries({ priceLineVisible: false });
    fund.setData((data.panels.funding ?? []).map((p) => ({
      time: ts(p.time), value: p.value, color: p.value >= 0 ? "#26a69a" : "#ef5350",
    })));
    fund.createPriceLine({ price: 0, color: "#8892b0", lineStyle: LineStyle.Dotted, lineWidth: 1, axisLabelVisible: false, title: "" });

    // --- sync time scales across all panes ---
    let syncing = false;
    const unsub = charts.map((chart, i) => {
      const handler = (range: unknown) => {
        if (syncing || !range) return;
        syncing = true;
        charts.forEach((o, j) => { if (i !== j) o.timeScale().setVisibleLogicalRange(range as never); });
        syncing = false;
      };
      chart.timeScale().subscribeVisibleLogicalRangeChange(handler);
      return () => chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler);
    });
    price.timeScale().fitContent();

    return () => {
      unsub.forEach((fn) => fn());
      charts.forEach((c) => c.remove());
    };
    } catch (e) {
      console.error("[charts] render failed:", e);
      charts.forEach((c) => { try { c.remove(); } catch { /* noop */ } });
      return () => {};
    }
  }, [data]);

  const Pane = ({ title, legend, inner }: { title: string; legend?: ReactNode; inner: RefObject<HTMLDivElement> }) => (
    <div className="chart-card">
      <div className="title"><span>{title}</span>{legend}</div>
      <div ref={inner} />
    </div>
  );
  const key = (color: string, text: string) => (
    <span className="legend-key"><span className="legend-swatch" style={{ background: color }} />{text}</span>
  );

  return (
    <>
      <Pane
        title={`${data.symbol} · ${data.timeframe} · price`}
        legend={<>{key("#58a6ff", "SMA 20")}{key("#e3b341", "EMA 20")}{key("#8892b0", "Bollinger 20·2")}</>}
        inner={priceRef}
      />
      <Pane title="Regime" legend={<span className="muted-txt">color = market state per bar</span>} inner={regimeRef} />
      <Pane title="RSI 14" inner={rsiRef} />
      <Pane title="MACD 12·26·9" legend={<>{key("#58a6ff", "MACD")}{key("#e3b341", "Signal")}</>} inner={macdRef} />
      <Pane title="ADX 14" legend={<>{key("#c9d1d9", "ADX")}{key("#26a69a", "+DI")}{key("#ef5350", "−DI")}</>} inner={adxRef} />
      <Pane title="Funding rate" legend={<span className="muted-txt">green = longs pay shorts</span>} inner={fundingRef} />
    </>
  );
}
