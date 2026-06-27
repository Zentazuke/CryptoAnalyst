import type { EnsembleRead } from "../types";

const LEAN_COLOR: Record<string, string> = {
  bullish: "#3fb950",
  bearish: "#f85149",
  neutral: "#8b949e",
};

const SIGNAL_LABEL: Record<string, string> = {
  ema_trend: "EMA trend",
  bb_position: "BB position",
  macd: "MACD",
  rsi_momentum: "RSI momentum",
  adx_di: "ADX / DI",
  regime: "Regime",
};

/** The calibrated directional ensemble: a weighted lean across the candle
 *  signals, presented honesty-first — its out-of-sample track record decides
 *  whether the lean is worth trusting on this timeframe. */
export function EnsembleCard({ ens, timeframe }: { ens: EnsembleRead; timeframe: string }) {
  const color = LEAN_COLOR[ens.lean] ?? "#8b949e";
  const cal = ens.calibration;
  const lift = cal?.lift ?? null;

  // the track record decides the framing, not the lean itself
  const edge =
    lift == null ? { txt: "not enough history to calibrate", tone: "#8b949e", trust: false }
    : lift >= 1.05 ? { txt: `measured edge (lift ${lift.toFixed(2)})`, tone: "#3fb950", trust: true }
    : lift >= 0.95 ? { txt: `no clear edge (lift ${lift.toFixed(2)})`, tone: "#d29922", trust: false }
    : { txt: `no edge on ${timeframe} (lift ${lift.toFixed(2)}) — treat as noise`, tone: "#f85149", trust: false };

  const pct = Math.max(-1, Math.min(1, ens.normalized));
  const fillLeft = pct >= 0 ? 50 : 50 + pct * 50;
  const fillWidth = Math.abs(pct) * 50;

  const signals = Object.entries(ens.signals);

  return (
    <div className="card ensemble">
      <div className="card-title">
        Directional ensemble <span className="muted-txt">· {ens.horizon}-bar horizon · {timeframe}</span>
      </div>

      <div className="ens-headline">
        <span className="ens-lean" style={{ color: edge.trust ? color : "#8b949e" }}>
          {ens.lean}
        </span>
        <span className="ens-badge" style={{ color: edge.tone, borderColor: edge.tone }}>{edge.txt}</span>
      </div>

      {/* agreement meter: how strongly the active signals point one way */}
      <div className="ens-meter" title={`net normalized score ${ens.normalized.toFixed(2)} (−1 all bearish … +1 all bullish)`}>
        <div className="ens-meter-mid" />
        <div className="ens-meter-fill" style={{ left: `${fillLeft}%`, width: `${fillWidth}%`, background: edge.trust ? color : "#8b949e" }} />
      </div>
      <div className="ens-meter-labels"><span>bearish</span><span>signal agreement</span><span>bullish</span></div>

      {cal && (
        <p className="ens-track">
          Out-of-sample: when this leaned a direction it was right{" "}
          <b style={{ color: edge.tone }}>{(cal.acc * 100).toFixed(0)}%</b> vs a {(cal.base * 100).toFixed(0)}% baseline
          {" "}(n={cal.n}). {edge.trust
            ? "A real, measured edge on this timeframe."
            : "Not a reliable directional call on this timeframe — weight it accordingly."}
        </p>
      )}

      <div className="ens-signals">
        {signals.map(([name, s]) => {
          const c = s.call > 0 ? "#3fb950" : s.call < 0 ? "#f85149" : "#8b949e";
          const dir = s.call > 0 ? "▲" : s.call < 0 ? "▼" : "·";
          return (
            <div key={name} className="ens-sig" title={s.train_acc != null ? `train accuracy ${(s.train_acc * 100).toFixed(0)}% (n=${s.train_n}); weight ${s.weight.toFixed(2)}` : "no weight (too few samples)"}>
              <span className="ens-sig-name">{SIGNAL_LABEL[name] ?? name}</span>
              <span className="ens-sig-dir" style={{ color: c }}>{dir}</span>
              <span className="ens-sig-wt" style={{ width: `${Math.min(100, Math.abs(s.weight) * 180)}%`, background: c }} />
            </div>
          );
        })}
      </div>
      <p className="ens-foot muted-txt">
        Each signal is weighted by its measured historical edge (learned on early data); a signal with no edge
        earns ~0 weight, an anti-predictive one a negative weight. Lean is the weighted vote of the live signals.
      </p>
    </div>
  );
}
