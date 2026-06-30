import type { Calibration, RegimeCurrent } from "../types";
import { regimeColor, regimeLabel } from "../regime";

/** A small badge stating whether the measured edge is statistically real. */
function CalVerdict({ verdict }: { verdict: NonNullable<Calibration["verdict"]> }) {
  const map: Record<string, { txt: string; cls: string }> = {
    edge: { txt: "significant edge", cls: "good-txt" },
    negative: { txt: "significantly worse", cls: "bad-txt" },
    "no-edge": { txt: "no clear edge", cls: "muted-txt" },
    insufficient: { txt: "insufficient sample", cls: "muted-txt" },
    "no-data": { txt: "no data", cls: "muted-txt" },
  };
  const v = map[verdict] ?? map["no-data"];
  return <span className={v.cls}> · {v.txt}</span>;
}

/** Current regime call: state, confidence, why, and how reliable that call has
 *  been historically (calibration lift from the backend). */
export function RegimeCard({ regime, timeframe }: { regime: RegimeCurrent; timeframe: string }) {
  const color = regimeColor(regime.label);
  const conf = Math.round(regime.confidence * 100);
  const cal = regime.calibration;

  return (
    <div className="card">
      <div className="card-title">Current regime · {timeframe}</div>

      <div className="regime-headline">
        <span className="regime-chip" style={{ background: color }} />
        <span className="regime-name" style={{ color }}>{regimeLabel(regime.label)}</span>
      </div>

      <div className="conf-row" title="How cleanly the tape fits this regime label — NOT a probability that price moves in this direction. For directional reliability, see the measured calibration below.">
        <span className="conf-label">regime fit</span>
        <div className="conf-track">
          <div className="conf-fill" style={{ width: `${conf}%`, background: color }} />
        </div>
        <span className="conf-val">{conf}%</span>
      </div>
      <p className="muted-txt" style={{ fontSize: 10.5, margin: "-6px 0 10px" }}>
        Fit confidence in the label — not a directional probability (it doesn't track which way price goes).
        Trust the measured reliability below.
      </p>

      <ul className="reasons">
        {regime.reasons.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>

      <div className="calibration">
        {cal && cal.hit_rate != null && cal.base_rate != null ? (
          <>
            <span className="cal-title">historical reliability</span>
            <span className="cal-detail">
              when called <b style={{ color }}>{regimeLabel(regime.label)}</b>, resolved as
              expected <b>{(cal.hit_rate * 100).toFixed(0)}%</b>
              {cal.ci_low != null && cal.ci_high != null && (
                <span className="muted-txt"> ({(cal.ci_low * 100).toFixed(0)}–{(cal.ci_high * 100).toFixed(0)}% CI)</span>
              )}{" "}
              vs <b>{(cal.base_rate * 100).toFixed(0)}%</b> base
              {cal.lift != null && (
                <> · lift <b className={cal.significant ? (cal.verdict === "edge" ? "good-txt" : "bad-txt") : "muted-txt"}>{cal.lift.toFixed(2)}×</b></>
              )}{" "}
              <span className="muted-txt">(n={cal.count}, h={regime.calibration_horizon})</span>
              {cal.verdict && <CalVerdict verdict={cal.verdict} />}
            </span>
          </>
        ) : (
          <span className="muted-txt">no calibration sample for this label</span>
        )}
      </div>
    </div>
  );
}
