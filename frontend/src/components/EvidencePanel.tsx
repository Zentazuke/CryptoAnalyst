import { useEffect, useState } from "react";
import { fetchExplain } from "../api";
import type { ExplainResponse, FiredSignal } from "../api";

/** P1.3 — the evidence-gated signal panel.
 *
 *  Every signal firing on the latest bar, WITH its receipts: measured accuracy
 *  vs base rate, CI, sample size, and both-halves stability. The gating rule
 *  is visual and blunt: RELIABLE rows are prominent; significant-but-unstable
 *  rows are dimmed context; uncalibrated rows are collapsed behind a drawer,
 *  because a read without receipts is decoration, not evidence. */

const READ_LABEL: Record<string, { txt: string; cls: string }> = {
  bullish: { txt: "reliable signals lean BULLISH", cls: "good-txt" },
  bearish: { txt: "reliable signals lean BEARISH", cls: "bad-txt" },
  mixed: { txt: "reliable signals DISAGREE — stand back", cls: "muted-txt" },
  "no-reliable-signal": { txt: "nothing reliable is firing", cls: "muted-txt" },
};

function pct(x?: number | null): string {
  return x == null ? "–" : `${(x * 100).toFixed(0)}%`;
}

function Row({ f }: { f: FiredSignal }) {
  const dirCls = f.direction === "bullish" ? "good-txt" : "bad-txt";
  const dim = !f.reliable;
  return (
    <tr style={dim ? { opacity: 0.55 } : undefined}>
      <td>{f.signal}</td>
      <td className={dirCls}>{f.direction}</td>
      <td>
        {f.accuracy != null ? (
          <>
            <b>{pct(f.accuracy)}</b>
            <span className="muted-txt"> vs {pct(f.base)} base</span>
          </>
        ) : (
          <span className="muted-txt">no sample</span>
        )}
      </td>
      <td className="muted-txt">
        {f.n != null ? `n=${f.n}` : "–"}
        {f.ci_low != null && f.ci_high != null && ` · ${pct(f.ci_low)}–${pct(f.ci_high)}`}
      </td>
      <td>
        {f.reliable ? (
          <b className="good-txt">RELIABLE</b>
        ) : f.significant ? (
          <span className="muted-txt">significant, unstable</span>
        ) : (
          <span className="muted-txt">{f.verdict}</span>
        )}
        {f.h1_acc != null && f.h2_acc != null && (
          <span className="muted-txt"> · H1/H2 {pct(f.h1_acc)}/{pct(f.h2_acc)}</span>
        )}
      </td>
    </tr>
  );
}

export function EvidencePanel({ symbol, timeframe }: { symbol: string; timeframe: string }) {
  const [data, setData] = useState<ExplainResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [showUnproven, setShowUnproven] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setData(null);
    fetchExplain(symbol, timeframe)
      .then((d) => alive && setData(d))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [symbol, timeframe]);

  if (loading && !data) {
    return (
      <div className="card">
        <div className="card-title">Signal evidence · {timeframe}</div>
        <p className="muted-txt">calibrating fired signals… (first load computes the full history)</p>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="card">
        <div className="card-title">Signal evidence · {timeframe}</div>
        <p className="muted-txt">evidence unavailable (API offline or not enough history)</p>
      </div>
    );
  }

  const withEvidence = data.fired.filter((f) => f.verdict !== "uncalibrated");
  const unproven = data.fired.filter((f) => f.verdict === "uncalibrated");
  const read = READ_LABEL[data.summary.read] ?? READ_LABEL["no-reliable-signal"];

  return (
    <div className="card">
      <div className="card-title">
        Signal evidence · {timeframe} · h={data.horizon} bars
      </div>

      <p style={{ margin: "4px 0 10px" }}>
        <b className={read.cls}>{read.txt}</b>
        <span className="muted-txt">
          {" "}
          · {data.summary.reliable_bullish} reliable bull / {data.summary.reliable_bearish} reliable
          bear / {data.summary.fired_total} firing
        </span>
      </p>

      {withEvidence.length > 0 ? (
        <table className="evidence-table" style={{ width: "100%", fontSize: 12, borderSpacing: 0 }}>
          <thead>
            <tr className="muted-txt" style={{ textAlign: "left" }}>
              <th>signal</th>
              <th>calls</th>
              <th>hit rate</th>
              <th>sample</th>
              <th>verdict</th>
            </tr>
          </thead>
          <tbody>
            {withEvidence.map((f) => (
              <Row key={f.signal} f={f} />
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted-txt">no calibrated signal is firing on the latest bar.</p>
      )}

      {unproven.length > 0 && (
        <p className="muted-txt" style={{ marginTop: 8, fontSize: 11 }}>
          <a
            style={{ cursor: "pointer", textDecoration: "underline" }}
            onClick={() => setShowUnproven((s) => !s)}
          >
            {showUnproven ? "hide" : "show"} {unproven.length} unproven (no receipts — decoration)
          </a>
          {showUnproven && (
            <span> · {unproven.map((f) => `${f.signal} (${f.direction})`).join(" · ")}</span>
          )}
        </p>
      )}

      <p className="footnote" style={{ marginTop: 8 }}>
        Weigh only RELIABLE rows (significant AND positive in both sample halves). Everything
        else reshuffles like luck — the project's postmortems are a graveyard of trusting it.
      </p>
    </div>
  );
}
