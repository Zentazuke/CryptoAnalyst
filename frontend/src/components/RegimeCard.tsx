import type { RegimeCurrent } from "../types";
import { regimeColor, regimeLabel } from "../regime";

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

      <div className="conf-row">
        <span className="conf-label">confidence</span>
        <div className="conf-track">
          <div className="conf-fill" style={{ width: `${conf}%`, background: color }} />
        </div>
        <span className="conf-val">{conf}%</span>
      </div>

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
              expected <b>{(cal.hit_rate * 100).toFixed(0)}%</b> of the time vs{" "}
              <b>{(cal.base_rate * 100).toFixed(0)}%</b> base
              {cal.lift != null && (
                <> · lift <b className={cal.lift >= 1 ? "good-txt" : "muted-txt"}>{cal.lift.toFixed(2)}×</b></>
              )}{" "}
              <span className="muted-txt">(n={cal.count}, h={regime.calibration_horizon})</span>
            </span>
          </>
        ) : (
          <span className="muted-txt">no calibration sample for this label</span>
        )}
      </div>
    </div>
  );
}
