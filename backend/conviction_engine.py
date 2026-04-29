"""
conviction_engine.py — Weighted multi-factor conviction scoring (0–10 scale)

SCORE BREAKDOWN (max 10)
─────────────────────────────────────────────────────
Factor                      Weight   Max pts
─────────────────────────────────────────────────────
1. Trend alignment (EMA)      25%      2.5
2. RSI momentum               15%      1.5
3. Volume breakout            20%      2.0
4. Smart money (options)      25%      2.5
5. Risk-reward ratio          15%      1.5
─────────────────────────────────────────────────────
TOTAL                        100%     10.0

Threshold:  >= 7   → HIGH CONVICTION (trade)
            5–6.9  → MODERATE       (watch)
            < 5    → LOW            (skip)
"""

import pandas as pd
import numpy as np


# ─────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────

def calculate_conviction(df: pd.DataFrame,
                         smart_money: dict | None = None,
                         weights: dict | None = None) -> dict:
    """
    Returns a conviction dict with component breakdown.

    smart_money  — output from smart_money.analyze()
    weights      — optional dynamic weights from learning loop
    """
    W = _merge_weights(weights)
    latest = df.iloc[-1]

    trend   = _trend_score(latest)          # 0–2.5
    rsi     = _rsi_score(latest)            # 0–1.5
    volume  = _volume_score(latest, df)     # 0–2.0
    sm      = _smart_money_score(smart_money)  # 0–2.5
    rr      = _risk_reward_score(df, smart_money)  # 0–1.5

    raw = (trend  * W["trend"]  +
           rsi    * W["rsi"]    +
           volume * W["volume"] +
           sm     * W["smart_money"] +
           rr     * W["risk_reward"])

    total = round(min(raw, 10.0), 2)

    return {
        "total":       total,
        "grade":       _grade(total),
        "components": {
            "trend":        round(trend,  2),
            "rsi":          round(rsi,    2),
            "volume":       round(volume, 2),
            "smart_money":  round(sm,     2),
            "risk_reward":  round(rr,     2),
        },
        "weights_used": W,
    }


# ─────────────────────────────────────────────
# COMPONENT SCORERS
# ─────────────────────────────────────────────

def _trend_score(row) -> float:
    """
    Max 2.5 pts.
    close > ema20 > ema50  → full bullish stack    = 2.5
    close > ema20          → partial                = 1.5
    close > ema50 only     → weak                  = 0.5
    """
    close, e20, e50 = row["close"], row["ema20"], row["ema50"]
    if close > e20 > e50:
        return 2.5
    elif close > e20:
        return 1.5
    elif close > e50:
        return 0.5
    return 0.0


def _rsi_score(row) -> float:
    """
    Max 1.5 pts.
    Sweet spot 55–65 (strong without overbought)   = 1.5
    Acceptable 45–55 or 65–70                      = 0.75
    Oversold / overbought                          = 0.0
    """
    rsi = row.get("rsi", 50)
    if 55 <= rsi <= 65:
        return 1.5
    elif 45 <= rsi < 55:
        return 0.75
    elif 65 < rsi <= 70:
        return 0.5
    return 0.0


def _volume_score(row, df: pd.DataFrame) -> float:
    """
    Max 2.0 pts.
    Compares today's volume to 20-day avg.
    >2× avg + price up    → 2.0 (strong breakout)
    1.5–2× avg            → 1.5
    1–1.5× avg            → 0.75
    < avg                 → 0.0
    """
    vol     = row.get("volume", 0)
    vol_avg = row.get("vol_avg", vol)
    if vol_avg == 0:
        return 0.0

    ratio = vol / vol_avg

    # price direction on the day
    prev_close = df.iloc[-2]["close"] if len(df) > 1 else row["close"]
    price_up   = row["close"] > prev_close

    if ratio >= 2.0 and price_up:
        return 2.0
    elif ratio >= 1.5:
        return 1.5
    elif ratio >= 1.0:
        return 0.75
    return 0.0


def _smart_money_score(sm: dict | None) -> float:
    """
    Max 2.5 pts from options smart money analysis.
    """
    if sm is None:
        return 1.25   # neutral when no options data

    bias  = sm.get("bias", sm.get("signal", "NEUTRAL"))
    score = sm.get("score", 0)

    if bias == "BULLISH":
        pcr = sm.get("pcr", 1.0)
        return min(2.5, 1.5 + (pcr - 1.0))
    elif bias == "BEARISH":
        return 0.0
    return 1.0   # RANGE / NEUTRAL


def _risk_reward_score(df: pd.DataFrame, sm: dict | None) -> float:
    """
    Max 1.5 pts.
    Uses ATR (14) as stop proxy and OI-based resistance as target.
    RR >= 3   → 1.5
    RR >= 2   → 1.0
    RR >= 1.5 → 0.5
    < 1.5     → 0.0
    """
    if len(df) < 15:
        return 0.5   # not enough data

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)

    atr   = tr.rolling(14).mean().iloc[-1]
    price = df.iloc[-1]["close"]

    stop_dist = atr * 1.5

    target = None
    if sm and sm.get("resistance"):
        target = sm["resistance"] - price
    elif sm and sm.get("support"):
        target = (price - sm["support"]) * 2   # symmetrical projection

    if target is None or target <= 0 or stop_dist == 0:
        return 0.5

    rr = target / stop_dist

    if rr >= 3.0:
        return 1.5
    elif rr >= 2.0:
        return 1.0
    elif rr >= 1.5:
        return 0.5
    return 0.0


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "trend":       2.5,
    "rsi":         1.5,
    "volume":      2.0,
    "smart_money": 2.5,
    "risk_reward": 1.5,
}

def _merge_weights(override: dict | None) -> dict:
    w = DEFAULT_WEIGHTS.copy()
    if override:
        w.update(override)
    # normalise so components sum to 10
    total = sum(w.values())
    return {k: round(v / total * 10, 4) for k, v in w.items()}


def _grade(score: float) -> str:
    if score >= 7:
        return "HIGH"
    elif score >= 5:
        return "MODERATE"
    return "LOW"
