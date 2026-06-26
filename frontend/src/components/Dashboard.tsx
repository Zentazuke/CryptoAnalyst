import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  LineStyle,
  type UTCTimestamp,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
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

// Hoisted so their identity is stable across re-renders — if these were defined
// inside Dashboard, each live update would remount the pane <div>s and orphan
// the charts attached to them (blank panes).
function Pane({ title, legend, inner }: { title: string; legend?: ReactNode; inner: RefObject<HTMLDivElement> }) {
  return (
    <div className="chart-card">
      <div className="title"><span>{title}</span>{legend}</div>
      <div ref={inner} />
    </div>
  );
}
const legendKey = (color: string, text: string) => (
  <span className="legend-key"><span className="legend-swatch" style={{ background: color }} />{text}</span>
);

const OVERLAYS: { key: string; color: string; width: 1 | 2 }[] = [
  { key: "bb_upper", color: "#4b5a78", width: 1 },
  { key: "bb_lower", color: "#4b5a78", width: 1 },
  { key: "bb_mid", color: "#8892b0", width: 1 },
  { key: "sma_20", color: "#58a6ff", width: 2 },
  { key: "ema_20", color: "#e3b341", width: 2 },
];

// Handles built once and kept alive; data updates flow through .setData() so the
// charts never tear down and rebuild (no flicker, and zoom/pan is preserved).
interface ChartHandles {
  charts: IChartApi[];
  candles: ISeriesApi<"Candlestick">;
  volume: ISeriesApi<"Histogram">;
  overlays: Record<string, ISeriesApi<"Line">>;
  ribbon: ISeriesApi<"Histogram">;
  rsiLine: ISeriesApi<"Line">;
  macdHist: ISeriesApi<"Histogram">;
  macdLine: ISeriesApi<"Line">;
  macdSignal: ISeriesApi<"Line">;
  adxLine: ISeriesApi<"Line">;
  plusDi: ISeriesApi<"Line">;
  minusDi: ISeriesApi<"Line">;
  fund: ISeriesApi<"Histogram">;
  levelLines: IPriceLine[];
}

export function Dashboard({ data }: { data: ChartResponse }) {
  const priceRef = useRef<HTMLDivElement>(null);
  const regimeRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const adxRef = useRef<HTMLDivElement>(null);
  const fundingRef = useRef<HTMLDivElement>(null);

  const handles = useRef<ChartHandles | null>(null);
  const lastInstrument = useRef<string>("");

  // ── build the charts once, on mount ──
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

      // --- price: candles + volume + Bollinger + MAs (empty; filled by the data effect) ---
      const candles = price.addCandlestickSeries({
        upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
        wickUpColor: "#26a69a", wickDownColor: "#ef5350",
      });
      const volume = price.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol" });
      price.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

      const overlays: Record<string, ISeriesApi<"Line">> = {};
      for (const o of OVERLAYS) {
        overlays[o.key] = price.addLineSeries({
          color: o.color, lineWidth: o.width, priceLineVisible: false, lastValueVisible: false,
        });
      }

      // --- regime ribbon ---
      const ribbon = regime.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
      regime.priceScale("right").applyOptions({ scaleMargins: { top: 0.1, bottom: 0 } });

      // --- RSI with static 70/30 guides ---
      const rsiLine = rsi.addLineSeries({ color: "#d29922", lineWidth: 2, priceLineVisible: false });
      for (const [p, col] of [[70, "#ef5350"], [30, "#26a69a"]] as const) {
        rsiLine.createPriceLine({ price: p, color: col, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: String(p) });
      }

      // --- MACD ---
      const macdHist = macd.addHistogramSeries({ priceLineVisible: false });
      const macdLine = macd.addLineSeries({ color: "#58a6ff", lineWidth: 2, priceLineVisible: false });
      const macdSignal = macd.addLineSeries({ color: "#e3b341", lineWidth: 1, priceLineVisible: false });

      // --- ADX with static 25 "trending" guide ---
      const adxLine = adx.addLineSeries({ color: "#c9d1d9", lineWidth: 2, priceLineVisible: false });
      adxLine.createPriceLine({ price: 25, color: "#8892b0", lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "25" });
      const plusDi = adx.addLineSeries({ color: "#26a69a", lineWidth: 1, priceLineVisible: false });
      const minusDi = adx.addLineSeries({ color: "#ef5350", lineWidth: 1, priceLineVisible: false });

      // --- funding: signed histogram with a static zero guide ---
      const fund = funding.addHistogramSeries({ priceLineVisible: false });
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

      handles.current = {
        charts, candles, volume, overlays, ribbon, rsiLine,
        macdHist, macdLine, macdSignal, adxLine, plusDi, minusDi, fund,
        levelLines: [],
      };

      return () => {
        unsub.forEach((fn) => fn());
        charts.forEach((c) => c.remove());
        handles.current = null;
        lastInstrument.current = "";
      };
    } catch (e) {
      console.error("[charts] build failed:", e);
      charts.forEach((c) => { try { c.remove(); } catch { /* noop */ } });
      return () => {};
    }
  }, []);

  // ── push new data into the existing series (no rebuild = no flicker) ──
  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    try {
      h.candles.setData(
        data.candles.map((c) => ({ time: ts(c.time), open: c.open, high: c.high, low: c.low, close: c.close })),
      );
      h.volume.setData(data.volume.map((v) => ({ time: ts(v.time), value: v.value, color: "#2b3340" })));
      for (const o of OVERLAYS) h.overlays[o.key]?.setData(toLine(data.overlays[o.key] ?? []));

      h.ribbon.setData(data.regime.map((r) => ({ time: ts(r.time), value: 1, color: regimeColor(r.label) })));

      h.rsiLine.setData(toLine(data.panels.rsi_14));

      h.macdHist.setData((data.panels.macd_hist ?? []).map((p) => ({
        time: ts(p.time), value: p.value, color: p.value >= 0 ? "#26a69a" : "#ef5350",
      })));
      h.macdLine.setData(toLine(data.panels.macd));
      h.macdSignal.setData(toLine(data.panels.macd_signal));

      h.adxLine.setData(toLine(data.panels.adx_14));
      h.plusDi.setData(toLine(data.panels.plus_di));
      h.minusDi.setData(toLine(data.panels.minus_di));

      h.fund.setData((data.panels.funding ?? []).map((p) => ({
        time: ts(p.time), value: p.value, color: p.value >= 0 ? "#26a69a" : "#ef5350",
      })));

      // structural levels change with the data — swap them out in place
      h.levelLines.forEach((l) => h.candles.removePriceLine(l));
      h.levelLines = [];
      const drawLevel = (lvl: { price: number; types: string[] }, color: string) => {
        h.levelLines.push(h.candles.createPriceLine({
          price: lvl.price, color, lineStyle: LineStyle.Dashed, lineWidth: 1,
          axisLabelVisible: true, title: lvl.types[0] ?? "",
        }));
      };
      (data.levels?.support ?? []).slice(0, 3).forEach((l) => drawLevel(l, "#2e7d46"));
      (data.levels?.resistance ?? []).slice(0, 3).forEach((l) => drawLevel(l, "#b3433b"));

      // only refit the view when the instrument/timeframe actually changes —
      // a live refresh of the same chart keeps your current zoom/pan.
      const inst = `${data.symbol}·${data.timeframe}`;
      if (inst !== lastInstrument.current) {
        h.charts[0].timeScale().fitContent();
        lastInstrument.current = inst;
      }
    } catch (e) {
      console.error("[charts] data update failed:", e);
    }
  }, [data]);

  return (
    <>
      <Pane
        title={`${data.symbol} · ${data.timeframe} · price`}
        legend={<>{legendKey("#58a6ff", "SMA 20")}{legendKey("#e3b341", "EMA 20")}{legendKey("#8892b0", "Bollinger 20·2")}</>}
        inner={priceRef}
      />
      <Pane title="Regime" legend={<span className="muted-txt">color = market state per bar</span>} inner={regimeRef} />
      <Pane title="RSI 14" inner={rsiRef} />
      <Pane title="MACD 12·26·9" legend={<>{legendKey("#58a6ff", "MACD")}{legendKey("#e3b341", "Signal")}</>} inner={macdRef} />
      <Pane title="ADX 14" legend={<>{legendKey("#c9d1d9", "ADX")}{legendKey("#26a69a", "+DI")}{legendKey("#ef5350", "−DI")}</>} inner={adxRef} />
      <Pane title="Funding rate" legend={<span className="muted-txt">green = longs pay shorts</span>} inner={fundingRef} />
    </>
  );
}
