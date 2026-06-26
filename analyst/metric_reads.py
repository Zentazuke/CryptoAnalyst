"""Per-metric analyst reads.

The main commentary fuses everything into one note. This module does the
opposite: it produces a *focused* read for each individual signal — current
regime, each indicator pane, microstructure, on-chain activity, market context,
and positioning — answering, for that one metric:

  * reading  — what it currently shows (grounded in the live value)
  * meaning  — the standard interpretation of that reading
  * outlook  — where it might go *based on that metric alone*, framed
               conditionally (never a guarantee)

Everything is deterministic and derived from values the engine already
computes; no LLM, no look-ahead.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from analyst.commentary import (
    BIAS, REGIME_TEXT, TF_HOURS, DEFAULT_HORIZON,
    _price, _pct, _dur, _crowd_read,
)
from analyst.crowd import calibrate_funding_contrarian
from analyst.features import snapshot
from analyst.levels import key_levels
from analyst.risk import risk_frame
from analyst.regime import calibrate, classify_latest


def _read(key, title, bias, reading, meaning, outlook) -> dict:
    return {"key": key, "title": title, "bias": bias,
            "reading": reading, "meaning": meaning, "outlook": outlook}


def _slope_word(now: float | None, prev: float | None, eps: float = 1e-9) -> str:
    if now is None or prev is None:
        return "flat"
    d = now - prev
    return "rising" if d > eps else "falling" if d < -eps else "flat"


def metric_reads(
    candles: list[Any], timeframe: str, *, micro: dict | None = None,
    sentiment: dict | None = None, funding_rows: list[dict] | None = None,
    positioning: dict | None = None, derivatives: dict | None = None,
    htf: dict | None = None, onchain: dict | None = None, horizon: int | None = None,
) -> list[dict]:
    """Ordered list of focused per-metric reads. Empty if history is too short."""
    if len(candles) < 60:
        return []

    horizon = horizon or DEFAULT_HORIZON.get(timeframe, 12)
    tfh = TF_HOURS.get(timeframe, 1)
    v = snapshot(candles)["values"]
    prev = snapshot(candles[:-1])["values"] if len(candles) > 61 else {}
    g, gp = v.get, prev.get

    closes = np.array([c["close"] if isinstance(c, dict) else c.close for c in candles], float)
    close = float(closes[-1])

    reads: list[dict] = []

    # ── Current regime ────────────────────────────────────────────────────
    reg = classify_latest(candles)
    cal = calibrate(candles, params={"horizon": horizon})["per_label"].get(reg.label)
    bias = BIAS.get(reg.label, "neutral")
    conf = int(reg.confidence * 100)
    win = _dur(horizon * tfh)
    if cal and cal.get("hit_rate") is not None and cal.get("lift") is not None:
        edge = (f"In similar conditions price has resolved as expected ~{cal['hit_rate'] * 100:.0f}% "
                f"of the time vs a {cal['base_rate'] * 100:.0f}% base rate (lift {cal['lift']:.2f}×, "
                f"n={cal['count']}).")
        edge_note = ("a modest but real measured edge" if cal["lift"] >= 1.15
                     else "little measured edge — treat the lean lightly")
    else:
        edge = "Too few historical samples to estimate an edge here."
        edge_note = "low confidence from sparse history"
    if reg.label in ("trend_up", "trend_down"):
        direction = "higher" if reg.label == "trend_up" else "lower"
        out = (f"Base case is continuation {direction} over the next ~{win} — trends tend to persist until "
               f"momentum/structure breaks. {edge} ({edge_note}).")
        mean = ("In a defined trend, pullbacks have tended to resolve in the trend's direction; "
                "fading it is the lower-probability trade.")
    elif reg.label == "range":
        out = (f"Base case is continued oscillation over ~{win}: mean-reversion toward the range middle "
               f"rather than a sustained breakout. {edge} ({edge_note}).")
        mean = "Without a trend, momentum signals are noisier and mean-reversion dominates."
    elif reg.label == "low_vol_drift":
        out = (f"Quiet drift is the base case over ~{win}, but compressed regimes often precede an "
               f"expansion — be ready for a larger move, direction unconfirmed. {edge}")
        mean = "Low volatility coils energy; the breakout direction is not yet decided."
    elif reg.label == "breakout":
        out = (f"A range break is underway; it either follows through or fails back inside. Confirmation is "
               f"holding the breakout level over ~{win}. {edge}")
        mean = "Breakouts resolve fast — confirmation (a hold) separates the real ones from traps."
    elif reg.label == "flash_risk":
        out = "Immediate direction is unreliable and slippage is high — wait for volatility to normalize before acting."
        mean = "A volatility shock distorts mechanical signals; the prudent stance is patience."
    else:
        out = "Conditions are undetermined; no actionable lean from the regime alone."
        mean = "The classifier can't pin a regime — other metrics carry more weight right now."
    reads.append(_read(
        "regime", "Current regime", bias,
        f"The model reads {REGIME_TEXT.get(reg.label, reg.label)} at {conf}% confidence.",
        mean, out,
    ))

    # ── Price action & levels ─────────────────────────────────────────────
    ema, sma, bb_u, bb_l, bb_m, atr = g("ema_20"), g("sma_20"), g("bb_upper"), g("bb_lower"), g("bb_mid"), g("atr_14")
    levels = key_levels(candles)
    nr, ns = levels.get("nearest_resistance"), levels.get("nearest_support")
    loc_bits = []
    if ema is not None:
        loc_bits.append(f"{'above' if close > ema else 'below'} the 20-EMA ({_price(ema)})")
    if bb_u is not None and bb_l is not None:
        if close > bb_u:
            loc_bits.append("above the upper Bollinger band (extended)")
        elif close < bb_l:
            loc_bits.append("below the lower Bollinger band (extended)")
        else:
            loc_bits.append("inside the Bollinger bands")
    reading = f"Price {_price(close)}" + (", " + ", ".join(loc_bits) + "." if loc_bits else ".")
    lvl_bits = []
    if nr:
        lvl_bits.append(f"resistance ~{_price(nr['price'])} ({nr['dist_atr']:+.1f} ATR)")
    if ns:
        lvl_bits.append(f"support ~{_price(ns['price'])} ({ns['dist_atr']:+.1f} ATR)")
    risk = risk_frame(candles, levels, horizon)
    out_bits = []
    if risk:
        out_bits.append(f"Expected 1σ move over ~{win}: ±{risk['expected_move_pct'] * 100:.1f}% "
                        f"(~{_price(risk['band_low'])}–{_price(risk['band_high'])}); volatility {risk['vol_regime']}.")
    if nr and ns:
        out_bits.append(f"The {_price(ns['price'])}–{_price(nr['price'])} band frames the next move: a break "
                        f"of either edge sets the near-term direction.")
    elif nr:
        out_bits.append(f"{_price(nr['price'])} is the level to clear for upside continuation.")
    elif ns:
        out_bits.append(f"{_price(ns['price'])} is the line that, if lost, opens downside.")
    reads.append(_read(
        "price", "Price action & levels",
        "bullish" if (ema is not None and close > ema) else "bearish" if ema is not None else "neutral",
        reading + (" Levels: " + "; ".join(lvl_bits) + "." if lvl_bits else ""),
        "Location relative to the moving average and bands says whether buyers or sellers hold the immediate "
        "advantage; the nearest levels are where that control is most likely to change hands.",
        " ".join(out_bits) or "No clean levels nearby — price has room to travel before structure intervenes.",
    ))

    # ── RSI (14) ──────────────────────────────────────────────────────────
    rsi, rsi_p = g("rsi_14"), gp("rsi_14")
    if rsi is not None:
        slope = _slope_word(rsi, rsi_p)
        if rsi >= 70:
            zone, rbias = "overbought", "bearish"
            mean = "Overbought readings flag stretched buying — upside often pauses or mean-reverts from here."
            out = ("A roll back under 70 would be the first sign momentum is cooling; in a strong uptrend RSI can "
                   "stay pinned high, so it's a caution flag, not a sell signal on its own.")
        elif rsi <= 30:
            zone, rbias = "oversold", "bullish"
            mean = "Oversold readings flag stretched selling — a bounce or at least a pause becomes more likely."
            out = ("A reclaim of 30–40 would confirm a relief bounce; in a strong downtrend RSI can stay depressed, "
                   "so wait for it to turn up before trusting it.")
        elif rsi >= 55:
            zone, rbias = "bullish-neutral", "bullish"
            mean = "Momentum favors buyers but isn't yet stretched."
            out = "A push toward 70 would extend the move; losing 50 would cede momentum back to sellers."
        elif rsi <= 45:
            zone, rbias = "bearish-neutral", "bearish"
            mean = "Momentum favors sellers but isn't yet washed out."
            out = "A slide toward 30 would extend the weakness; reclaiming 50 would shift momentum back to buyers."
        else:
            zone, rbias = "neutral", "neutral"
            mean = "Momentum is balanced — no edge to either side from RSI right now."
            out = "Watch for a break above 55 (buyers take over) or below 45 (sellers take over)."
        reads.append(_read(
            "rsi", "RSI (14)", rbias,
            f"RSI is {rsi:.0f} ({zone}) and {slope}.", mean, out,
        ))

    # ── MACD ──────────────────────────────────────────────────────────────
    macd, sig, hist, hist_p = g("macd"), g("macd_signal"), g("macd_hist"), gp("macd_hist")
    if macd is not None and sig is not None:
        above = macd > sig
        h = hist or 0.0
        hist_slope = _slope_word(hist, hist_p)
        building = (h >= 0 and hist_slope == "rising") or (h < 0 and hist_slope == "falling")
        mbias = "bullish" if above else "bearish"
        reads.append(_read(
            "macd", "MACD (12·26·9)", mbias,
            f"MACD is {'above' if above else 'below'} its signal line with a "
            f"{'positive' if h >= 0 else 'negative'} histogram that is {hist_slope}.",
            f"MACD {'above' if above else 'below'} signal points to {'upward' if above else 'downward'} "
            f"momentum on this timeframe; the histogram measures how fast that momentum is "
            f"{'building' if building else 'fading'}.",
            ("Momentum is accelerating in the trend's direction — supportive of continuation while the "
             "histogram keeps expanding." if building else
             "The histogram is contracting toward zero — momentum is fading; a cross of the signal line "
             "would flag the next shift in control."),
        ))

    # ── ADX (14) ──────────────────────────────────────────────────────────
    adx, adx_p, pdi, mdi = g("adx_14"), gp("adx_14"), g("plus_di"), g("minus_di")
    if adx is not None:
        slope = _slope_word(adx, adx_p)
        up = (pdi is not None and mdi is not None and pdi > mdi)
        dir_word = "buyers (+DI over −DI)" if up else "sellers (−DI over +DI)"
        if adx >= 40:
            strength, abias = "a very strong trend", ("bullish" if up else "bearish")
            mean = f"A powerful trend led by {dir_word}; counter-trend trades are low-probability here."
            out = ("Very high ADX is also late-stage — it eventually rolls over, so watch for it to peak and "
                   "turn down as the first sign of trend exhaustion.")
        elif adx >= 25:
            strength, abias = "a defined trend", ("bullish" if up else "bearish")
            mean = f"A confirmed trend led by {dir_word}; pullbacks have tended to resolve in its direction."
            out = (f"While ADX is {slope} the trend is {'strengthening' if slope == 'rising' else 'losing steam' if slope == 'falling' else 'holding'}; "
                   "a drop back under 25 would mark a shift to range conditions.")
        elif adx < 20:
            strength, abias = "no real trend", "neutral"
            mean = "Below 20 means range/chop — momentum signals are noisier and mean-reversion dominates."
            out = "A rise back above 25 (with a +DI/−DI separation) would signal a new trend starting to form."
        else:
            strength, abias = "a developing, unconfirmed trend", ("bullish" if up else "bearish")
            mean = "Between 20–25 the trend is forming but not yet confirmed."
            out = "A push above 25 would confirm it; a fade below 20 would put price back into range behavior."
        reads.append(_read(
            "adx", "ADX (14)", abias,
            f"ADX is {adx:.0f} ({strength}) and {slope}" + (f", with {dir_word}." if abias != "neutral" else "."),
            mean, out,
        ))

    # ── Funding (perp) ────────────────────────────────────────────────────
    fr_now = (derivatives or {}).get("funding_rate")
    if fr_now is None and micro:
        fr_now = micro.get("funding_rate")
    if fr_now is not None:
        recent = []
        for r in (funding_rows or [])[-12:]:
            val = r.get("v", r.get("funding_rate"))
            if val is not None:
                recent.append(float(val))
        avg = float(np.mean(recent)) if recent else fr_now
        persistent = len(recent) >= 6 and all(x > 0 for x in recent[-6:]) or (recent and all(x < 0 for x in recent[-6:]))
        fbias = "bearish" if fr_now > 0 else "bullish" if fr_now < 0 else "neutral"  # contrarian
        reads.append(_read(
            "funding", "Funding rate", fbias,
            f"Funding is {fr_now * 100:+.4f}%/8h"
            + (f" (recent avg {avg * 100:+.4f}%)." if recent else ".")
            + (" It has stayed one-sided for several periods." if persistent else ""),
            ("Positive funding = longs pay shorts (crowd leans long); negative = shorts pay longs (crowd leans "
             "short). It's a positioning/contrarian gauge, not a direction call."),
            ("Persistently positive funding is fuel for downside liquidation flushes if price stalls — "
             "contrarian-bearish." if fr_now > 0 and persistent else
             "Persistently negative funding sets up short-squeeze risk on any upside surprise — "
             "contrarian-bullish." if fr_now < 0 and persistent else
             "Funding is mild/cheap — little crowding either way, so it adds little contrarian signal right now."),
        ))

    # ── Microstructure (order book) ───────────────────────────────────────
    if micro:
        sp, b = micro.get("spread_bps"), micro.get("basis_bps")
        bid, ask = micro.get("bid_depth_quote"), micro.get("ask_depth_quote")
        imb = None
        if bid is not None and ask is not None and (bid + ask) > 0:
            imb = (bid - ask) / (bid + ask)
        bits = []
        if sp is not None:
            bits.append(f"spread {sp:.2f} bps ({'wide — thin liquidity' if sp > 3 else 'tight — deep liquidity'})")
        if imb is not None:
            side = "bid-heavy" if imb > 0.05 else "ask-heavy" if imb < -0.05 else "balanced"
            bits.append(f"book {imb * 100:+.0f}% ({side})")
        if b is not None:
            bits.append(f"basis {b:+.1f} bps ({'contango' if b > 0 else 'backwardation'})")
        mbias = "bullish" if (imb is not None and imb > 0.05) else "bearish" if (imb is not None and imb < -0.05) else "neutral"
        reads.append(_read(
            "microstructure", "Microstructure", mbias,
            ("Order book: " + ", ".join(bits) + ".") if bits else "Live order-book snapshot available.",
            "Spread gauges liquidity (slippage cost); book imbalance shows which side has more resting size "
            "right now; basis shows whether perps trade rich or cheap to spot.",
            ("Resting bids outweigh asks — short-term support, though book imbalance is shallow and can flip in "
             "seconds." if mbias == "bullish" else
             "Resting asks outweigh bids — short-term overhead supply, but it's a fast-moving, shallow signal." if mbias == "bearish" else
             "Book is balanced — no near-term order-flow edge; treat this as liquidity context, not direction."),
        ))

    # ── Positioning & derivatives (crowd) ─────────────────────────────────
    pos = positioning or (sentiment.get("positioning") if sentiment else None)
    dv = derivatives or (sentiment.get("derivatives") if sentiment else None)
    crowd = _crowd_read(pos, dv) if (pos or dv) else None
    if crowd:
        crowd_cal = calibrate_funding_contrarian(candles, funding_rows, horizon) if funding_rows else None
        meaning = crowd.get("meaning") or "Positioning is balanced — no contrarian edge from the crowd right now."
        if crowd_cal and crowd_cal.get("lift") is not None:
            meaning += (f" Measured: funding-crowding has been contrarian {crowd_cal['hit_rate'] * 100:.0f}% of "
                        f"the time vs a {crowd_cal['base_rate'] * 100:.0f}% base (lift {crowd_cal['lift']:.2f}×, "
                        f"n={crowd_cal['count']}).")
        cb = crowd.get("bias")
        if cb == "bearish":
            out = "If the crowd stays crowded long into resistance, a liquidation flush lower is the contrarian risk."
        elif cb == "bullish":
            out = "If the crowd stays crowded short, a squeeze higher is the contrarian risk on any upside surprise."
        else:
            out = "Balanced positioning adds little — watch for a build-up of one-sided crowding to create a contrarian setup."
        reads.append(_read(
            "positioning", "Positioning & derivatives", cb or "neutral",
            crowd["happening"], meaning, out,
        ))

    # ── Market context (macro backdrop) ───────────────────────────────────
    ctx = (sentiment or {}).get("context") or {}
    fg, fgl, dom = ctx.get("fear_greed_value"), ctx.get("fear_greed_label"), ctx.get("btc_dominance_pct")
    mc = ctx.get("market_cap_change_24h_pct")
    if fg is not None or dom is not None or mc is not None:
        bits = []
        if fg is not None:
            bits.append(f"Fear & Greed {fg:.0f}{f' ({fgl})' if fgl else ''}")
        if dom is not None:
            bits.append(f"BTC dominance {dom:.1f}%")
        if mc is not None:
            bits.append(f"total mkt cap {mc:+.1f}% 24h")
        if fg is not None and fg <= 25:
            cbias, mean = "bullish", ("Extreme fear has historically clustered near local bottoms — a "
                                      "contrarian-bullish backdrop.")
            out = "Capitulation lows form in extreme fear; a turn up in F&G would confirm sentiment is mending."
        elif fg is not None and fg >= 75:
            cbias, mean = "bearish", "Extreme greed signals froth — late-stage moves are more reversal-prone."
            out = "Rallies built on greed are fragile; a roll-over in F&G often precedes a cooling-off."
        else:
            cbias, mean = "neutral", "Sentiment is in neutral territory — no contrarian extreme to lean on."
            out = "Watch the extremes (≤25 fear / ≥75 greed) for a contrarian signal; mid-range adds little."
        if mc is not None and dom is not None:
            out += (" Rising dominance with a soft tape usually means capital is hiding in BTC over alts."
                    if dom and mc < 0 else "")
        reads.append(_read(
            "market_context", "Market context", cbias,
            ", ".join(bits) + ".", mean, out,
        ))

    # ── On-chain network activity ─────────────────────────────────────────
    if onchain and onchain.get("available", True):
        at = onchain.get("addr_trend_30d")
        pctl = onchain.get("addr_percentile_90d")
        div = onchain.get("divergence")
        if at is not None or div:
            reading = ""
            if at is not None:
                reading = (f"Active addresses {at * 100:+.0f}% over 30d"
                           + (f" ({pctl * 100:.0f}th percentile of the 90d range)." if pctl is not None else "."))
            if div == "bullish":
                obias = "bullish"
                mean = "Network activity is rising while price falls — a bullish divergence suggesting accumulation/usage is building."
                out = "Constructive divergences often precede a price catch-up, but on-chain is slow-moving — it's a backdrop, not a trigger."
            elif div == "bearish":
                obias = "bearish"
                mean = "Activity is fading while price rises — a lower-quality rally that can run out of fuel."
                out = "Watch for price to converge down to weakening fundamentals; on-chain leads slowly, so allow time."
            else:
                obias = "neutral"
                mean = "Network usage is tracking price — no divergence to exploit."
                out = "A divergence (activity rising into falling price, or vice-versa) is the signal to watch for here."
            reads.append(_read(
                "onchain", "On-chain activity", obias,
                reading or "On-chain network-activity snapshot available.", mean, out,
            ))

    return reads
