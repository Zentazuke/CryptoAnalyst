"""Deterministic analyst commentary.

Composes a human-readable note from the metrics the engine already computes —
no LLM, no hidden magic. Three sections plus an honest outlook:

  * what's happening — observed price/trend/momentum/volatility/positioning
  * what it means    — the standard interpretation of those readings
  * outlook          — a probabilistic lean grounded in the regime's *measured*
                       calibration (hit-rate vs base rate), with an explicit
                       invalidation level and a caveat. Never a guarantee.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from analyst.features import snapshot
from analyst.regime import calibrate, classify_latest
from analyst.regime import classifier as C

TF_HOURS = {
    "1m": 1 / 60, "5m": 5 / 60, "15m": 0.25, "30m": 0.5,
    "1h": 1, "4h": 4, "12h": 12, "1D": 24, "7D": 168,
}
DEFAULT_HORIZON = {"1h": 24, "4h": 12, "12h": 8, "1D": 5, "7D": 4}

BIAS = {
    C.TREND_UP: "bullish", C.TREND_DOWN: "bearish", C.RANGE: "neutral",
    C.LOW_VOL_DRIFT: "neutral", C.BREAKOUT: "directional", C.FLASH_RISK: "high-risk",
}
REGIME_TEXT = {
    C.TREND_UP: "an up-trend", C.TREND_DOWN: "a down-trend", C.RANGE: "a range",
    C.LOW_VOL_DRIFT: "a low-volatility drift", C.BREAKOUT: "a breakout",
    C.FLASH_RISK: "a volatility shock", C.UNKNOWN: "an undetermined state",
}


def _price(x: float) -> str:
    if x >= 100:
        return f"${x:,.0f}"
    if x >= 1:
        return f"${x:,.2f}"
    return f"${x:,.4f}"


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def _dur(hours: float) -> str:
    if hours < 1:
        return f"{int(round(hours * 60))} min"
    if hours < 48:
        return f"{hours:.0f} hours"
    return f"{hours / 24:.0f} days"


def _closes(candles: list[Any]) -> np.ndarray:
    return np.array([c["close"] if isinstance(c, dict) else c.close for c in candles], float)


def _sentiment_bias(label: str | None) -> str:
    if not label:
        return "neutral"
    low = label.lower()
    if "bull" in low:
        return "bullish"
    if "bear" in low:
        return "bearish"
    return "neutral"


def generate_commentary(
    candles: list[Any], timeframe: str, micro: dict | None = None,
    horizon: int | None = None, sentiment: dict | None = None,
) -> dict:
    if len(candles) < 60:
        return {
            "headline": "Not enough history for a reliable read.",
            "whats_happening": [], "what_it_means": [],
            "outlook": {"bias": "neutral", "confidence": "n/a", "text": "Ingest more data.", "invalidation": None},
            "caveat": "",
        }

    snap = snapshot(candles)["values"]
    reg = classify_latest(candles)
    horizon = horizon or DEFAULT_HORIZON.get(timeframe, 12)
    cal = calibrate(candles, params={"horizon": horizon})["per_label"].get(reg.label)

    closes = _closes(candles)
    close = float(closes[-1])
    tfh = TF_HOURS.get(timeframe, 1)
    lookback = min(horizon, len(closes) - 1)
    chg = close / closes[-1 - lookback] - 1.0

    g = snap.get
    ema, sma = g("ema_20"), g("sma_20")
    rsi, adx, pdi, mdi = g("rsi_14"), g("adx_14"), g("plus_di"), g("minus_di")
    macd, macd_sig, hist = g("macd"), g("macd_signal"), g("macd_hist")
    bb_u, bb_l, bb_m = g("bb_upper"), g("bb_lower"), g("bb_mid")
    atr = g("atr_14")

    happening: list[str] = []
    meaning: list[str] = []

    # --- price & location ---
    happening.append(
        f"Price is {_price(close)}, {_pct(chg)} over the last {lookback} bars (~{_dur(lookback * tfh)})."
    )
    if ema is not None:
        happening.append(f"It is trading {'above' if close > ema else 'below'} the 20-period EMA ({_price(ema)}).")

    # --- trend ---
    if adx is not None:
        if adx >= 25 and pdi is not None and mdi is not None:
            up = pdi > mdi
            happening.append(f"ADX is {adx:.0f} with {'+DI over -DI' if up else '-DI over +DI'} - a defined {'up' if up else 'down'}trend.")
            meaning.append(f"A defined {'up' if up else 'down'}trend means pullbacks have tended to resolve in the trend's direction; fading it is the lower-probability trade.")
        elif adx < 20:
            happening.append(f"ADX is {adx:.0f} (below 20) — no real trend; price is ranging or chopping.")
            meaning.append("Without a trend, momentum signals are noisier and mean-reversion toward the middle of the range dominates.")
        else:
            happening.append(f"ADX is {adx:.0f} — a developing but unconfirmed trend.")

    # --- momentum ---
    if rsi is not None:
        if rsi >= 70:
            happening.append(f"RSI is {rsi:.0f} (overbought).")
            meaning.append("Overbought RSI flags stretched buying — near-term upside may be limited or due a pause.")
        elif rsi <= 30:
            happening.append(f"RSI is {rsi:.0f} (oversold).")
            meaning.append("Oversold RSI flags stretched selling — a bounce or at least a pause becomes more likely.")
        else:
            happening.append(f"RSI is {rsi:.0f} (neutral).")
    if macd is not None and macd_sig is not None:
        above = macd > macd_sig
        happening.append(f"MACD is {'above' if above else 'below'} its signal line ({'positive' if (hist or 0) >= 0 else 'negative'} histogram).")
        meaning.append(f"MACD {'above' if above else 'below'} signal points to {'upward' if above else 'downward'} momentum on this timeframe.")

    # --- volatility / bands ---
    if bb_u is not None and bb_l is not None:
        if close > bb_u:
            happening.append(f"Price is above the upper Bollinger band ({_price(bb_u)}) — statistically extended.")
            meaning.append("Closes outside the upper band tend to mean-revert unless a strong trend keeps pushing.")
        elif close < bb_l:
            happening.append(f"Price is below the lower Bollinger band ({_price(bb_l)}) — extended to the downside.")
            meaning.append("Closes below the lower band often see a relief bounce back toward the band middle.")

    # --- regime ---
    happening.append(f"The model reads the regime as {REGIME_TEXT.get(reg.label, reg.label)} (confidence {int(reg.confidence * 100)}%).")

    # --- positioning (microstructure) ---
    if micro:
        f, b, sp = micro.get("funding_rate"), micro.get("basis_bps"), micro.get("spread_bps")
        if f is not None:
            happening.append(f"Perp funding is {f * 100:+.4f}% — {'longs pay shorts (crowded longs)' if f > 0 else 'shorts pay longs (crowded shorts)'}.")
            meaning.append(
                "Crowded longs add fuel for downside liquidation cascades." if f > 0
                else "Crowded shorts set up squeeze risk if price ticks higher."
            )
        if b is not None:
            happening.append(f"Perp basis is {b:+.1f} bps ({'contango' if b > 0 else 'backwardation'} vs index).")
        if sp is not None and sp > 3:
            happening.append(f"Top-of-book spread is wide ({sp:.1f} bps) — thinner liquidity, more slippage risk.")

    # --- sentiment & context (from the sentiment engine, if available) ---
    sent_bias = None
    if sentiment and sentiment.get("outlook"):
        ol = sentiment["outlook"]
        label = ol.get("label")
        sent_bias = _sentiment_bias(label)
        score, conf = ol.get("outlook_score"), ol.get("confidence")
        bits = f"Sentiment outlook is {label}" if label else "Sentiment outlook available"
        if score is not None:
            bits += f" (score {score:+.2f}{f', confidence {conf:.0%}' if isinstance(conf, (int, float)) else ''})"
        happening.append(bits + ".")
        ctx = sentiment.get("context") or {}
        fg, fgl, dom = ctx.get("fear_greed_value"), ctx.get("fear_greed_label"), ctx.get("btc_dominance_pct")
        if fg is not None:
            happening.append(f"Fear & Greed is {fg:.0f}{f' ({fgl})' if fgl else ''}" + (f"; BTC dominance {dom:.1f}%." if dom is not None else "."))
            if fg <= 25:
                meaning.append("Extreme fear has historically clustered near local bottoms — contrarian-bullish context.")
            elif fg >= 75:
                meaning.append("Extreme greed signals froth — late-stage moves are more reversal-prone.")
        dp = sentiment.get("direction_prob_6h")
        if dp is not None:
            happening.append(f"The engine's learned 6h up-probability (sentiment + positioning) is {dp:.0%}.")
        alerts = sentiment.get("alerts") or {}
        shock = alerts.get("shock") or alerts.get("level") or alerts.get("alert")
        if shock and str(shock).lower() not in ("none", "false", "calm", "normal"):
            happening.append(f"Shock alert: {shock}.")
            meaning.append("An active panic/euphoria shock means headline-driven volatility — be cautious with mechanical signals.")

    outlook = _outlook(reg, cal, horizon, timeframe, close, ema, bb_m, bb_u, bb_l, chg)
    _apply_confluence(outlook, BIAS.get(reg.label, "neutral"), sent_bias)
    headline = _headline(reg, outlook, close)

    return {
        "headline": headline,
        "whats_happening": happening,
        "what_it_means": meaning,
        "outlook": outlook,
        "caveat": (
            "This is a probabilistic read of current conditions, not a forecast. Short-horizon "
            "crypto direction is hard to predict — size and manage risk accordingly."
        ),
    }


def _outlook(reg, cal, horizon, timeframe, close, ema, bb_m, bb_u, bb_l, chg) -> dict:
    bias = BIAS.get(reg.label, "neutral")
    tfh = TF_HOURS.get(timeframe, 1)
    window = _dur(horizon * tfh)

    # calibration-grounded odds phrasing
    if cal and cal.get("hit_rate") is not None and cal.get("base_rate") is not None:
        hit = cal["hit_rate"] * 100
        base = cal["base_rate"] * 100
        lift = cal.get("lift")
        if lift and lift >= 1.15:
            edge = f"about {hit:.0f}% of the time vs a {base:.0f}% base rate (lift {lift:.2f}× — a modest but real historical edge)"
            conf = "medium" if lift >= 1.3 and reg.confidence >= 0.3 else "low-to-medium"
        else:
            edge = f"about {hit:.0f}% of the time, barely better than the {base:.0f}% base rate (little measured edge here)"
            conf = "low"
    else:
        edge = "with too few historical samples to estimate reliably"
        conf = "low"

    if reg.label in (C.TREND_UP, C.TREND_DOWN):
        direction = "higher" if reg.label == C.TREND_UP else "lower"
        text = (
            f"Base case is continuation {direction} over the next ~{window}. When the model flagged "
            f"{REGIME_TEXT[reg.label]} in similar conditions, price extended that way {edge}."
        )
        inval_level = ema if ema is not None else bb_m
        if inval_level is not None:
            cross = "back above" if reg.label == C.TREND_DOWN else "back below"
            invalidation = f"A {timeframe} close {cross} ~{_price(inval_level)} (the 20-EMA) would neutralize this lean."
        else:
            invalidation = None
    elif reg.label == C.RANGE:
        text = (
            f"Base case is continued oscillation over the next ~{window} — mean-reversion toward the "
            f"range middle rather than a sustained breakout. Range calls historically resolved as expected {edge}."
        )
        if bb_u is not None and bb_l is not None:
            invalidation = f"A decisive {timeframe} close outside {_price(bb_l)}–{_price(bb_u)} (the Bollinger band) would signal a regime change to watch."
        else:
            invalidation = None
    elif reg.label == C.LOW_VOL_DRIFT:
        text = (
            f"Volatility is compressed; the base case is more quiet drift over the next ~{window}, but "
            f"low-vol regimes often precede an expansion — be ready for a bigger move, direction unknown."
        )
        invalidation = "A sharp expansion in range/ATR would mark the end of this regime."
    elif reg.label == C.BREAKOUT:
        text = (
            f"A range break is in progress {('higher' if chg >= 0 else 'lower')}. Breakouts either follow "
            f"through or fail back into the range — confirmation is a hold of the breakout level over ~{window}. "
            f"Historically these resolved as expected {edge}."
        )
        invalidation = f"A close back inside the prior range (toward {_price(bb_m)}) would flag a failed break." if bb_m is not None else None
    elif reg.label == C.FLASH_RISK:
        text = (
            "A volatility shock just hit. Immediate direction is unreliable and slippage is high; the prudent "
            "stance is to wait for the dust to settle rather than chase."
        )
        conf = "low"
        invalidation = "Re-assess once volatility normalizes and a clearer regime forms."
    else:
        text = "Conditions are undetermined; no actionable lean."
        invalidation = None

    return {"bias": bias, "confidence": conf, "horizon_bars": horizon, "text": text, "invalidation": invalidation}


def _apply_confluence(outlook: dict, tech_bias: str, sent_bias: str | None) -> None:
    """Fuse the technical bias with the sentiment bias into the outlook text."""
    if sent_bias is None:
        return
    directional = {"bullish", "bearish"}
    tech_dir = tech_bias if tech_bias in directional else None
    if tech_dir and sent_bias in directional:
        if tech_dir == sent_bias:
            outlook["text"] += (
                f" Confluence: technicals and sentiment both lean {sent_bias} — that agreement raises conviction."
            )
            outlook["confidence"] = "medium" if outlook["confidence"] in ("low", "low-to-medium") else outlook["confidence"]
        else:
            outlook["text"] += (
                f" Divergence: price structure is {tech_dir} while sentiment is {sent_bias}. "
                "Divergences often precede volatility or a reversal — treat the directional lean cautiously."
            )
            outlook["confidence"] = "low"
    elif sent_bias in directional:
        outlook["text"] += f" Sentiment is {sent_bias}, a {('supportive' if sent_bias == tech_bias else 'contextual')} backdrop to the {tech_bias} technical read."
    outlook["sentiment_bias"] = sent_bias


def _headline(reg, outlook, close) -> str:
    bias = outlook["bias"]
    state = REGIME_TEXT.get(reg.label, reg.label)
    lead = {
        "bullish": "Constructive", "bearish": "Heavy", "neutral": "Rangebound",
        "directional": "Breaking out", "high-risk": "Volatile",
    }.get(bias, "Mixed")
    return f"{lead}: the tape is in {state} ({outlook['confidence']} conviction)."
