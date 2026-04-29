"""
strategies.py — Six production-grade trading strategies

Each strategy returns a unified signal dict or None.

Signal schema
─────────────────────────────────────────────────────────
{
  "strategy":    str           strategy identifier
  "direction":   LONG | SHORT
  "entry":       float         recommended entry price
  "target":      float         profit target
  "stop":        float         stop-loss level
  "rr":          float         risk-reward ratio
  "duration":    int           max holding days
  "confidence":  float         0-10
  "reasons":     list[str]     plain-English rationale bullets
}
─────────────────────────────────────────────────────────

Strategies implemented
  1. EMA_TREND_FOLLOW   — multi-EMA stack + MACD + Supertrend
  2. BB_SQUEEZE_BREAK   — Bollinger squeeze → explosive breakout
  3. RSI_DIVERGENCE     — hidden bullish divergence reversal
  4. VWAP_MOMENTUM      — VWAP reclaim + volume surge
  5. ADX_BREAKOUT       — ADX > 25 trend continuation
  6. STOCH_REVERSAL     — oversold stochastic with OBV confirmation
"""

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────
# PUBLIC: score all strategies for one stock
# ─────────────────────────────────────────────

def score_all(df: pd.DataFrame, smart_money: dict | None = None) -> list[dict]:
    """
    Run all strategies. Returns list of active signals sorted by confidence.
    A stock can trigger multiple strategies simultaneously.
    """
    fns = [
        _ema_trend_follow,
        _bb_squeeze_break,
        _rsi_divergence,
        _vwap_momentum,
        _adx_breakout,
        _stoch_reversal,
    ]
    signals = []
    for fn in fns:
        try:
            sig = fn(df, smart_money)
            if sig:
                signals.append(sig)
        except Exception:
            pass

    return sorted(signals, key=lambda x: x["confidence"], reverse=True)


def best_signal(df: pd.DataFrame, smart_money: dict | None = None) -> dict | None:
    """Return the single highest-confidence signal, or None."""
    sigs = score_all(df, smart_money)
    return sigs[0] if sigs else None


# ─────────────────────────────────────────────
# STRATEGY 1 — EMA TREND FOLLOW
# ─────────────────────────────────────────────

def _ema_trend_follow(df: pd.DataFrame, sm: dict | None) -> dict | None:
    """
    Classic 3-EMA stack with MACD and Supertrend confirmation.
    Condition: close > ema9 > ema20 > ema50
               MACD histogram positive and rising
               Supertrend bullish
    """
    r = df.iloc[-1]
    p = df.iloc[-2]

    bullish_stack = r["close"] > r["ema9"] > r["ema20"] > r["ema50"]
    macd_up       = r["macd_hist"] > 0 and r["macd_hist"] > p["macd_hist"]
    supertrend_ok = r["supertrend_dir"] == 1
    adx_ok        = r["adx"] > 20

    if not (bullish_stack and macd_up and supertrend_ok):
        return None

    conf = 5.0
    if adx_ok:           conf += 1.0
    if r["vol_ratio"] > 1.3: conf += 1.0
    if sm and sm.get("bias") == "BULLISH": conf += 1.0
    if r["close"] > r["ema200"]: conf += 1.0
    conf = min(conf, 10.0)

    entry  = round(r["close"], 2)
    stop   = round(r["supertrend"], 2)           # supertrend acts as trailing stop
    risk   = entry - stop
    target = round(entry + 2.5 * risk, 2)        # 2.5:1 RR

    if risk <= 0 or target <= entry:
        return None

    return _signal(
        strategy   = "EMA_TREND_FOLLOW",
        direction  = "LONG",
        entry      = entry,
        target     = target,
        stop       = stop,
        duration   = 10,
        confidence = round(conf, 1),
        reasons    = [
            f"Triple EMA stack bullish (close {entry} > EMA9 {round(r['ema9'],1)} > EMA20 {round(r['ema20'],1)} > EMA50 {round(r['ema50'],1)})",
            f"MACD histogram positive and rising ({round(r['macd_hist'],2)})",
            f"Supertrend bullish (stop at {stop})",
            f"ADX {round(r['adx'],1)} {'— strong trend' if adx_ok else '— weak trend'}",
        ]
    )


# ─────────────────────────────────────────────
# STRATEGY 2 — BOLLINGER SQUEEZE BREAKOUT
# ─────────────────────────────────────────────

def _bb_squeeze_break(df: pd.DataFrame, sm: dict | None) -> dict | None:
    """
    Detects Bollinger Band squeeze (low volatility → contraction) followed
    by an explosive breakout above the upper band with volume surge.
    """
    r   = df.iloc[-1]
    p   = df.iloc[-2]

    # squeeze: BB width in lowest 20% of last 50 bars
    hist_width = df["bb_width"].iloc[-50:] if len(df) >= 50 else df["bb_width"]
    squeeze    = r["bb_width"] < hist_width.quantile(0.20)

    # breakout: close above upper band today, was inside yesterday
    breakout   = r["close"] > r["bb_upper"] and p["close"] <= p["bb_upper"]
    vol_surge  = r["vol_ratio"] > 1.8

    if not (squeeze or breakout) or not vol_surge:
        return None
    if not (r["close"] > r["ema20"]):      # must be above mid-term trend
        return None

    atr  = r["atr"]
    conf = 5.5
    if breakout:          conf += 1.5
    if squeeze:           conf += 1.0
    if r["vol_ratio"] > 2.5: conf += 1.0
    if sm and sm.get("bias") == "BULLISH": conf += 0.5
    conf = min(conf, 10.0)

    entry  = round(r["close"], 2)
    stop   = round(r["bb_mid"] - 0.5 * atr, 2)    # back below mid = invalidation
    risk   = entry - stop
    target = round(entry + 2.0 * risk, 2)

    if risk <= 0:
        return None

    return _signal(
        strategy   = "BB_SQUEEZE_BREAK",
        direction  = "LONG",
        entry      = entry,
        target     = target,
        stop       = stop,
        duration   = 7,
        confidence = round(conf, 1),
        reasons    = [
            f"Bollinger squeeze detected (width {round(r['bb_width']*100,1)}% at 20th percentile)",
            f"Price {'broke above upper band' if breakout else 'approaching upper band'}",
            f"Volume surge {round(r['vol_ratio'],1)}× average",
            f"Stop at BB midline {round(r['bb_mid'],1)}",
        ]
    )


# ─────────────────────────────────────────────
# STRATEGY 3 — RSI BULLISH DIVERGENCE
# ─────────────────────────────────────────────

def _rsi_divergence(df: pd.DataFrame, sm: dict | None) -> dict | None:
    """
    Hidden bullish divergence: price makes lower low, RSI makes higher low.
    Classic institutional accumulation signal. Works best at support.
    """
    r = df.iloc[-1]

    if not r.get("rsi_bull_div", False):
        return None
    if r["rsi"] > 55:               # must still be in lower RSI zone
        return None

    conf = 6.0
    if r["rsi"] < 40:               conf += 1.0      # stronger if deeply oversold
    if r["vol_ratio"] > 1.2:        conf += 0.5
    if r["close"] > r["ema50"]:     conf += 0.5      # long-term support intact
    if r["supertrend_dir"] == 1:    conf += 1.0
    if sm and sm.get("bias") == "BULLISH": conf += 1.0
    conf = min(conf, 10.0)

    atr    = r["atr"]
    entry  = round(r["close"], 2)
    stop   = round(entry - 1.5 * atr, 2)
    risk   = entry - stop
    target = round(entry + 2.5 * risk, 2)

    return _signal(
        strategy   = "RSI_DIVERGENCE",
        direction  = "LONG",
        entry      = entry,
        target     = target,
        stop       = stop,
        duration   = 8,
        confidence = round(conf, 1),
        reasons    = [
            f"Bullish RSI divergence: price at lower low, RSI at higher low ({round(r['rsi'],1)})",
            f"Classic institutional accumulation pattern",
            f"1.5×ATR stop at {stop}",
            f"Supertrend {'bullish' if r['supertrend_dir']==1 else 'bearish'}",
        ]
    )


# ─────────────────────────────────────────────
# STRATEGY 4 — VWAP MOMENTUM
# ─────────────────────────────────────────────

def _vwap_momentum(df: pd.DataFrame, sm: dict | None) -> dict | None:
    """
    Price reclaims VWAP from below with volume surge.
    Institutions use VWAP as a benchmark — reclaim = they're back buying.
    """
    r   = df.iloc[-1]
    p   = df.iloc[-2]

    reclaim    = r["close"] > r["vwap"] and p["close"] <= p["vwap"]
    vol_surge  = r["vol_ratio"] > 1.5
    macd_pos   = r["macd_hist"] > 0

    if not (reclaim and vol_surge):
        return None

    conf = 5.0
    if macd_pos:             conf += 1.0
    if r["adx"] > 20:        conf += 1.0
    if r["rsi"] < 65:        conf += 0.5      # not overbought
    if r["close"] > r["ema20"]: conf += 1.0
    if sm and sm.get("bias") == "BULLISH": conf += 1.0
    if r["vol_ratio"] > 2.0: conf += 0.5
    conf = min(conf, 10.0)

    atr    = r["atr"]
    entry  = round(r["close"], 2)
    stop   = round(r["vwap"] - 0.5 * atr, 2)    # below VWAP = signal fails
    risk   = entry - stop
    target = round(entry + 2.0 * risk, 2)

    if risk <= 0:
        return None

    return _signal(
        strategy   = "VWAP_MOMENTUM",
        direction  = "LONG",
        entry      = entry,
        target     = target,
        stop       = stop,
        duration   = 5,
        confidence = round(conf, 1),
        reasons    = [
            f"Price reclaimed VWAP ({round(r['vwap'],1)}) with {round(r['vol_ratio'],1)}× volume",
            f"Institutional benchmark crossed — buy pressure confirmed",
            f"MACD {'positive' if macd_pos else 'negative'}",
            f"Stop below VWAP at {stop}",
        ]
    )


# ─────────────────────────────────────────────
# STRATEGY 5 — ADX TREND CONTINUATION
# ─────────────────────────────────────────────

def _adx_breakout(df: pd.DataFrame, sm: dict | None) -> dict | None:
    """
    Strong trend (ADX > 25) + minor pullback to EMA20 + bounce.
    Buy the dip in a strong trend — highest probability setup.
    """
    r   = df.iloc[-1]
    p   = df.iloc[-2]

    strong_trend  = r["adx"] > 25
    bullish_super = r["supertrend_dir"] == 1
    # pullback: touched EMA20 in last 3 bars then bounced
    recent        = df.iloc[-4:-1]
    touched_ema20 = (recent["low"] <= recent["ema20"]).any()
    bounced       = r["close"] > r["ema20"] and r["close"] > p["close"]

    if not (strong_trend and bullish_super and touched_ema20 and bounced):
        return None

    conf = 6.0
    if r["adx"] > 35:        conf += 1.0
    if r["macd_hist"] > 0:   conf += 0.5
    if r["vol_ratio"] > 1.2: conf += 0.5
    if r["close"] > r["ema50"]: conf += 0.5
    if sm and sm.get("bias") == "BULLISH": conf += 1.0
    conf = min(conf, 10.0)

    atr    = r["atr"]
    entry  = round(r["close"], 2)
    stop   = round(r["ema20"] - atr * 0.5, 2)
    risk   = entry - stop
    target = round(entry + 3.0 * risk, 2)      # higher RR on strong trends

    if risk <= 0:
        return None

    return _signal(
        strategy   = "ADX_BREAKOUT",
        direction  = "LONG",
        entry      = entry,
        target     = target,
        stop       = stop,
        duration   = 12,
        confidence = round(conf, 1),
        reasons    = [
            f"Strong trend: ADX {round(r['adx'],1)} > 25",
            f"Pullback to EMA20 ({round(r['ema20'],1)}) and bounced",
            f"Supertrend bullish — trend direction confirmed",
            f"3:1 RR target at {target}, stop at {stop}",
        ]
    )


# ─────────────────────────────────────────────
# STRATEGY 6 — STOCHASTIC REVERSAL
# ─────────────────────────────────────────────

def _stoch_reversal(df: pd.DataFrame, sm: dict | None) -> dict | None:
    """
    Stochastic oversold (<20) with %K crossing above %D + OBV rising.
    Short-term mean reversion — fastest signal with 3-5 day duration.
    """
    r   = df.iloc[-1]
    p   = df.iloc[-2]

    oversold   = r["stoch_k"] < 25 and r["stoch_d"] < 25
    k_cross    = r["stoch_k"] > r["stoch_d"] and p["stoch_k"] <= p["stoch_d"]
    obv_rising = r["obv"] > r["obv_ema"]           # smart money still buying
    not_down   = r["supertrend_dir"] != -1          # don't fight strong downtrend

    if not (oversold and k_cross and obv_rising and not_down):
        return None

    conf = 5.5
    if r["rsi"] < 40:           conf += 1.0
    if r["close"] > r["ema50"]: conf += 1.0
    if r["vol_ratio"] > 1.2:    conf += 0.5
    if sm and sm.get("bias") == "BULLISH": conf += 0.5
    if r["rsi_bull_div"]:       conf += 1.0
    conf = min(conf, 10.0)

    atr    = r["atr"]
    entry  = round(r["close"], 2)
    stop   = round(entry - 1.2 * atr, 2)
    risk   = entry - stop
    target = round(entry + 2.0 * risk, 2)

    return _signal(
        strategy   = "STOCH_REVERSAL",
        direction  = "LONG",
        entry      = entry,
        target     = target,
        stop       = stop,
        duration   = 4,
        confidence = round(conf, 1),
        reasons    = [
            f"Stochastic oversold: K={round(r['stoch_k'],1)}, D={round(r['stoch_d'],1)}",
            f"%K crossed above %D — momentum turning up",
            f"OBV above OBV-EMA — accumulation detected",
            f"Short-term reversal target {target} (4-day hold)",
        ]
    )


# ─────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────

def _signal(strategy, direction, entry, target, stop, duration, confidence, reasons) -> dict:
    risk = entry - stop   if direction == "LONG"  else stop - entry
    rr   = round((target - entry) / risk, 2) if risk > 0 else 0
    return {
        "strategy":   strategy,
        "direction":  direction,
        "entry":      entry,
        "target":     target,
        "stop":       stop,
        "rr":         rr,
        "duration":   duration,
        "confidence": confidence,
        "reasons":    reasons,
    }
