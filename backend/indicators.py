"""
indicators.py — Full professional indicator suite

Indicators computed
────────────────────────────────────────────────────────────
EMA 9/20/50/200    Trend alignment across timeframes
MACD               Momentum + signal crossovers
RSI(14)            Overbought/oversold + divergence
Bollinger Bands    Volatility squeeze detection
ATR(14)            True volatility — drives stop/target sizing
ADX(14)            Trend strength (>25 = trending)
Supertrend         Trailing stop / trend direction
VWAP               Intraday institutional reference price
Volume OBV         On-Balance Volume — smart money accumulation
Stochastic         Short-term momentum confirmation
"""

import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)

    # ── EMA stack ────────────────────────────────────────────
    for span in [9, 20, 50, 200]:
        df[f"ema{span}"] = df["close"].ewm(span=span, adjust=False).mean()

    # ── RSI(14) ──────────────────────────────────────────────
    delta  = df["close"].diff()
    gain   = delta.clip(lower=0)
    loss   = (-delta).clip(lower=0)
    avg_g  = gain.ewm(com=13, adjust=False).mean()
    avg_l  = loss.ewm(com=13, adjust=False).mean()
    rs     = avg_g / avg_l.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # ── MACD(12,26,9) ────────────────────────────────────────
    ema12          = df["close"].ewm(span=12, adjust=False).mean()
    ema26          = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"]     = ema12 - ema26
    df["macd_sig"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]= df["macd"] - df["macd_sig"]

    # ── Bollinger Bands(20, 2σ) ──────────────────────────────
    df["bb_mid"]   = df["close"].rolling(20).mean()
    bb_std         = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
    df["bb_pct"]   = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    # ── ATR(14) ──────────────────────────────────────────────
    hl  = df["high"] - df["low"]
    hc  = (df["high"] - df["close"].shift()).abs()
    lc  = (df["low"]  - df["close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df["atr"] = tr.ewm(com=13, adjust=False).mean()

    # ── ADX(14) ──────────────────────────────────────────────
    df["adx"] = _adx(df)

    # ── Supertrend(10, 3) ────────────────────────────────────
    df = _supertrend(df, period=10, multiplier=3)

    # ── OBV ──────────────────────────────────────────────────
    direction     = np.sign(df["close"].diff()).fillna(0)
    df["obv"]     = (direction * df["volume"]).cumsum()
    df["obv_ema"] = df["obv"].ewm(span=20, adjust=False).mean()

    # ── Stochastic(14,3) ─────────────────────────────────────
    low14        = df["low"].rolling(14).min()
    high14       = df["high"].rolling(14).max()
    df["stoch_k"]= 100 * (df["close"] - low14) / (high14 - low14).replace(0, np.nan)
    df["stoch_d"]= df["stoch_k"].rolling(3).mean()

    # ── Volume ───────────────────────────────────────────────
    df["vol_avg"]  = df["volume"].rolling(20).mean()
    df["vol_ratio"]= df["volume"] / df["vol_avg"].replace(0, np.nan)

    # ── VWAP (rolling 20-bar proxy for daily VWAP) ───────────
    typical        = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"]     = (typical * df["volume"]).rolling(20).sum() / df["volume"].rolling(20).sum()

    # ── RSI divergence flag ──────────────────────────────────
    df["rsi_bull_div"] = _rsi_divergence(df, bullish=True)
    df["rsi_bear_div"] = _rsi_divergence(df, bullish=False)

    return df


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up   = high.diff()
    down = -low.diff()
    dm_p = pd.Series(np.where((up > down) & (up > 0), up, 0), index=df.index)
    dm_m = pd.Series(np.where((down > up) & (down > 0), down, 0), index=df.index)

    tr   = pd.concat([high - low,
                      (high - close.shift()).abs(),
                      (low  - close.shift()).abs()], axis=1).max(axis=1)

    tr_s  = tr.ewm(com=n-1,  adjust=False).mean()
    dmp_s = dm_p.ewm(com=n-1, adjust=False).mean()
    dmm_s = dm_m.ewm(com=n-1, adjust=False).mean()

    di_p = 100 * dmp_s / tr_s.replace(0, np.nan)
    di_m = 100 * dmm_s / tr_s.replace(0, np.nan)
    dx   = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, np.nan)
    return dx.ewm(com=n-1, adjust=False).mean()


def _supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3) -> pd.DataFrame:
    hl2 = (df["high"] + df["low"]) / 2
    atr = df["atr"]
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    st     = pd.Series(index=df.index, dtype=float)
    st_dir = pd.Series(index=df.index, dtype=int)   # 1=bullish, -1=bearish

    for i in range(1, len(df)):
        prev_up  = upper.iloc[i-1]
        prev_lo  = lower.iloc[i-1]
        cur_up   = upper.iloc[i]
        cur_lo   = lower.iloc[i]
        close    = df["close"].iloc[i]
        prev_st  = st.iloc[i-1] if i > 1 else cur_up

        final_up = min(cur_up, prev_up) if df["close"].iloc[i-1] <= prev_up else cur_up
        final_lo = max(cur_lo, prev_lo) if df["close"].iloc[i-1] >= prev_lo else cur_lo

        if prev_st == prev_up:
            st.iloc[i]     = final_up if close <= final_up else final_lo
            st_dir.iloc[i] = -1       if close <= final_up else 1
        else:
            st.iloc[i]     = final_lo if close >= final_lo else final_up
            st_dir.iloc[i] = 1        if close >= final_lo else -1

    df["supertrend"]     = st
    df["supertrend_dir"] = st_dir.fillna(1)
    return df


def _rsi_divergence(df: pd.DataFrame, bullish: bool = True, lookback: int = 14) -> pd.Series:
    """Simple swing-based divergence flag on last 14 bars."""
    result = pd.Series(False, index=df.index)
    for i in range(lookback, len(df)):
        window = df.iloc[i-lookback:i+1]
        if bullish:
            price_low_now  = window["close"].iloc[-1] < window["close"].iloc[:-1].min()
            rsi_low_now    = window["rsi"].iloc[-1]   > window["rsi"].iloc[:-1].min()
            result.iloc[i] = price_low_now and rsi_low_now
        else:
            price_hi_now   = window["close"].iloc[-1] > window["close"].iloc[:-1].max()
            rsi_hi_now     = window["rsi"].iloc[-1]   < window["rsi"].iloc[:-1].max()
            result.iloc[i] = price_hi_now and rsi_hi_now
    return result
