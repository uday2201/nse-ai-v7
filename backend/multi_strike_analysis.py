"""
multi_strike_analysis.py — Strike-Level Put-Call Analysis

Goes beyond aggregate PCR to analyse each strike individually.
Detects market maker expected ranges, key support/resistance,
and directional bias with far more precision than index PCR.

Key analyses
────────────────────────────────────────────────────────────
STRIKE PCR MAP       PCR at each strike (not aggregate)
                     Strikes with PCR > 2 = strong support
                     Strikes with PCR < 0.5 = strong resistance

MARKET MAKER RANGE   Range where MM is short gamma (max pain zone)
                     Price tends to be pinned here near expiry

SKEW ANALYSIS        OTM put IV vs OTM call IV
                     High put skew = market fearful / buying insurance
                     Low put skew = complacency

PAIN CHART           Full max pain calculation across all strikes
                     Where option buyers lose most money

CE/PE RATIO TREND    Track ratio changing intraday
                     Falling PCR intraday = bearish shift
                     Rising PCR intraday = bullish shift

SUPPORT LEVELS       Top 5 PE OI strikes = institutional support
RESISTANCE LEVELS    Top 5 CE OI strikes = institutional resistance

KEY ZONE             The strike with most total (CE+PE) OI
                     = highest activity = market's focal point
"""

import sqlite3
import json
import numpy as np
from datetime import datetime, date
from nsepython import nse_optionchain_scrapper
import pandas as pd

DB = "trades.db"


# ═══════════════════════════════════════════════════════════════
# DB SCHEMA
# ═══════════════════════════════════════════════════════════════

def init_multi_strike_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS strike_analysis (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol          TEXT,
            expiry          TEXT,
            spot            REAL,
            analysis        TEXT,   -- full JSON
            computed_at     TEXT
        );

        CREATE TABLE IF NOT EXISTS pcr_intraday (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT,
            pcr         REAL,
            ce_oi       REAL,
            pe_oi       REAL,
            timestamp   TEXT
        );
    """)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# MAIN: FULL MULTI-STRIKE ANALYSIS
# ═══════════════════════════════════════════════════════════════

def analyse_multi_strike(symbol: str = "NIFTY") -> dict:
    """
    Complete strike-level analysis for a symbol.
    Returns all levels, PCR map, skew, MM range, key zones.
    """
    try:
        data    = nse_optionchain_scrapper(symbol)
    except Exception as e:
        return {"error": str(e), "symbol": symbol}

    records = data.get("records", {})
    spot    = float(records.get("underlyingValue", 0) or 0)
    expiry  = records.get("expiryDates", [""])[0]
    rows    = records.get("data", [])

    if not rows or spot <= 0:
        return {"error": "No data", "symbol": symbol}

    # Build strike table
    strikes = _build_strike_table(rows, spot)
    if not strikes:
        return {"error": "No strikes parsed", "symbol": symbol}

    df = pd.DataFrame(strikes)

    result = {
        "symbol":        symbol,
        "spot":          spot,
        "expiry":        expiry,
        "computed_at":   datetime.utcnow().isoformat(),

        # Core metrics
        "aggregate_pcr": _aggregate_pcr(df),
        "pcr_map":       _strike_pcr_map(df, spot),
        "max_pain":      _max_pain(df),

        # Levels
        "support_levels":    _top_pe_strikes(df, n=5),
        "resistance_levels": _top_ce_strikes(df, n=5),
        "key_zone":          _key_zone(df),

        # MM range
        "mm_range":      _mm_range(df, spot),

        # Skew
        "skew":          _skew_analysis(df, spot),

        # PCR trend (stored intraday)
        "pcr_trend":     _get_pcr_trend(symbol),

        # Full strike data (top 20 by OI)
        "top_strikes":   _top_strikes_table(df, spot, n=20),

        # Summary
        "bias":          None,  # filled below
        "summary":       None,
    }

    result["bias"]    = _compute_bias(result)
    result["summary"] = _summarise(result)

    # Store intraday PCR
    _store_pcr(symbol, result["aggregate_pcr"]["pcr"],
               result["aggregate_pcr"]["total_ce_oi"],
               result["aggregate_pcr"]["total_pe_oi"])

    # Save to DB
    _save_analysis(symbol, expiry, spot, result)

    return result


# ═══════════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════════

def _build_strike_table(rows: list, spot: float) -> list[dict]:
    strikes = []
    for row in rows:
        strike = float(row.get("strikePrice", 0))
        if not strike:
            continue

        ce_oi    = float((row.get("CE") or {}).get("openInterest",         0) or 0)
        ce_iv    = float((row.get("CE") or {}).get("impliedVolatility",    0) or 0)
        ce_chg   = float((row.get("CE") or {}).get("changeinOpenInterest", 0) or 0)
        ce_ltp   = float((row.get("CE") or {}).get("lastPrice",            0) or 0)
        pe_oi    = float((row.get("PE") or {}).get("openInterest",         0) or 0)
        pe_iv    = float((row.get("PE") or {}).get("impliedVolatility",    0) or 0)
        pe_chg   = float((row.get("PE") or {}).get("changeinOpenInterest", 0) or 0)
        pe_ltp   = float((row.get("PE") or {}).get("lastPrice",            0) or 0)

        total_oi = ce_oi + pe_oi
        pcr      = round(pe_oi / ce_oi, 3) if ce_oi > 0 else 0
        moneyness= round((strike - spot) / spot * 100, 2)

        strikes.append({
            "strike":    strike,
            "ce_oi":     ce_oi,  "ce_iv": ce_iv,  "ce_chg": ce_chg,  "ce_ltp": ce_ltp,
            "pe_oi":     pe_oi,  "pe_iv": pe_iv,  "pe_chg": pe_chg,  "pe_ltp": pe_ltp,
            "total_oi":  total_oi,
            "pcr":       pcr,
            "moneyness": moneyness,
        })
    return sorted(strikes, key=lambda x: x["strike"])


def _aggregate_pcr(df: pd.DataFrame) -> dict:
    total_ce = df["ce_oi"].sum()
    total_pe = df["pe_oi"].sum()
    pcr      = round(total_pe / total_ce, 3) if total_ce > 0 else 0
    return {
        "pcr":        pcr,
        "total_ce_oi":int(total_ce),
        "total_pe_oi":int(total_pe),
        "bias":       "BULLISH" if pcr > 1.2 else "BEARISH" if pcr < 0.8 else "NEUTRAL",
    }


def _strike_pcr_map(df: pd.DataFrame, spot: float) -> list[dict]:
    """PCR at each strike with interpretation."""
    result = []
    for _, row in df.iterrows():
        pcr = row["pcr"]
        if pcr >= 2.0:    interp = "STRONG SUPPORT — heavy put writing"
        elif pcr >= 1.5:  interp = "SUPPORT — more puts than calls"
        elif pcr >= 1.0:  interp = "MILD SUPPORT"
        elif pcr >= 0.7:  interp = "MILD RESISTANCE"
        elif pcr >= 0.4:  interp = "RESISTANCE — more calls than puts"
        else:             interp = "STRONG RESISTANCE — heavy call writing"

        result.append({
            "strike":    int(row["strike"]),
            "pcr":       round(pcr, 2),
            "ce_oi":     int(row["ce_oi"]),
            "pe_oi":     int(row["pe_oi"]),
            "moneyness": row["moneyness"],
            "interpretation": interp,
        })
    return result


def _max_pain(df: pd.DataFrame) -> dict:
    """Max pain: strike where total option buyer loss is maximised."""
    strikes = df["strike"].tolist()
    pain    = {}

    for s in strikes:
        ce_loss = df.apply(lambda r: max(0, s - r["strike"]) * r["ce_oi"], axis=1).sum()
        pe_loss = df.apply(lambda r: max(0, r["strike"] - s) * r["pe_oi"], axis=1).sum()
        pain[s] = ce_loss + pe_loss

    mp_strike = min(pain, key=pain.get) if pain else 0

    # Zone: strikes within 1% of max pain
    zone_lo = mp_strike * 0.99
    zone_hi = mp_strike * 1.01

    return {
        "max_pain_strike": int(mp_strike),
        "zone_low":        int(zone_lo),
        "zone_high":       int(zone_hi),
        "interpretation":  f"Price tends to gravitate toward ₹{int(mp_strike)} near expiry (option buyer pain maximised here)",
    }


def _top_pe_strikes(df: pd.DataFrame, n: int = 5) -> list[dict]:
    """Top N strikes by PE OI = institutional support levels."""
    top = df.nlargest(n, "pe_oi")
    return [{"strike": int(r["strike"]), "pe_oi": int(r["pe_oi"]),
             "pe_iv": round(r["pe_iv"], 1), "label": "SUPPORT"} for _, r in top.iterrows()]


def _top_ce_strikes(df: pd.DataFrame, n: int = 5) -> list[dict]:
    """Top N strikes by CE OI = institutional resistance levels."""
    top = df.nlargest(n, "ce_oi")
    return [{"strike": int(r["strike"]), "ce_oi": int(r["ce_oi"]),
             "ce_iv": round(r["ce_iv"], 1), "label": "RESISTANCE"} for _, r in top.iterrows()]


def _key_zone(df: pd.DataFrame) -> dict:
    """Strike with highest TOTAL OI = market's focal point."""
    top = df.loc[df["total_oi"].idxmax()]
    return {
        "strike":   int(top["strike"]),
        "total_oi": int(top["total_oi"]),
        "ce_oi":    int(top["ce_oi"]),
        "pe_oi":    int(top["pe_oi"]),
        "label":    "KEY ZONE — highest activity",
    }


def _mm_range(df: pd.DataFrame, spot: float) -> dict:
    """
    Market Maker expected range.
    MM is short gamma between max CE and max PE strike.
    They hedge aggressively outside this range.
    """
    max_ce_strike = int(df.loc[df["ce_oi"].idxmax(), "strike"])
    max_pe_strike = int(df.loc[df["pe_oi"].idxmax(), "strike"])

    low  = min(max_ce_strike, max_pe_strike)
    high = max(max_ce_strike, max_pe_strike)

    width_pct = round((high - low) / spot * 100, 1)
    spot_pct  = round((spot - low) / (high - low) * 100, 1) if high != low else 50

    return {
        "lower":       low,
        "upper":       high,
        "width_pct":   width_pct,
        "spot_in_range": low <= spot <= high,
        "spot_position_pct": spot_pct,
        "interpretation": (
            f"MM expected range: ₹{low} – ₹{high} ({width_pct}% width). "
            f"Spot is {'inside' if low <= spot <= high else 'OUTSIDE'} range. "
            f"{'Gamma squeeze risk if spot breaks out.' if low <= spot <= high else 'MM hedging actively — expect volatility.'}"
        ),
    }


def _skew_analysis(df: pd.DataFrame, spot: float) -> dict:
    """
    Volatility skew: OTM put IV minus OTM call IV.
    High positive skew = market buying downside protection (fear).
    """
    otm_pe = df[(df["strike"] < spot * 0.97) & (df["pe_iv"] > 0)].nlargest(3, "pe_oi")
    otm_ce = df[(df["strike"] > spot * 1.03) & (df["ce_iv"] > 0)].nlargest(3, "ce_oi")

    avg_pe_iv = otm_pe["pe_iv"].mean() if not otm_pe.empty else 0
    avg_ce_iv = otm_ce["ce_iv"].mean() if not otm_ce.empty else 0

    skew = round(avg_pe_iv - avg_ce_iv, 2)

    if skew > 8:    skew_signal = "HIGH_FEAR — market buying heavy put protection"
    elif skew > 3:  skew_signal = "MODERATE_FEAR — normal skew, mild protection buying"
    elif skew > -2: skew_signal = "NEUTRAL_SKEW — balanced vol"
    else:           skew_signal = "REVERSE_SKEW — more call buying than put buying (bullish)"

    return {
        "otm_put_iv":  round(avg_pe_iv, 2),
        "otm_call_iv": round(avg_ce_iv, 2),
        "skew":        skew,
        "signal":      skew_signal,
    }


def _get_pcr_trend(symbol: str) -> list[dict]:
    """Intraday PCR trend — is it rising or falling?"""
    conn = _conn()
    rows = conn.execute("""
        SELECT pcr, ce_oi, pe_oi, timestamp FROM pcr_intraday
        WHERE symbol=? AND timestamp > date('now', '-1 day')
        ORDER BY id DESC LIMIT 20
    """, (symbol,)).fetchall()
    conn.close()
    return [{"pcr": r[0], "ce_oi": r[1], "pe_oi": r[2], "time": r[3][:16]} for r in reversed(rows)]


def _top_strikes_table(df: pd.DataFrame, spot: float, n: int = 20) -> list[dict]:
    """Top strikes by total OI for the full table view."""
    top = df.nlargest(n, "total_oi")
    result = []
    for _, r in top.iterrows():
        result.append({
            "strike":    int(r["strike"]),
            "moneyness": r["moneyness"],
            "ce_oi":     int(r["ce_oi"]),   "ce_iv": round(r["ce_iv"], 1),
            "pe_oi":     int(r["pe_oi"]),   "pe_iv": round(r["pe_iv"], 1),
            "pcr":       round(r["pcr"], 2),
            "ce_chg":    int(r["ce_chg"]),  "pe_chg": int(r["pe_chg"]),
            "total_oi":  int(r["total_oi"]),
        })
    return result


def _compute_bias(result: dict) -> str:
    score = 0
    pcr   = result["aggregate_pcr"]["pcr"]
    if pcr > 1.3:  score += 2
    elif pcr > 1.0:score += 1
    elif pcr < 0.7:score -= 2
    elif pcr < 1.0:score -= 1

    skew = result["skew"]["skew"]
    if skew > 5:   score -= 1   # fear = selling pressure
    elif skew < 0: score += 1   # calm = bullish

    mp = result["max_pain"]["max_pain_strike"]
    spot = result["spot"]
    if spot < mp:  score += 1   # spot below max pain = gravitates up
    elif spot > mp:score -= 1

    if score >= 2:   return "BULLISH"
    elif score <= -2:return "BEARISH"
    return "NEUTRAL"


def _summarise(result: dict) -> str:
    sym  = result["symbol"]
    spot = result["spot"]
    pcr  = result["aggregate_pcr"]["pcr"]
    mp   = result["max_pain"]["max_pain_strike"]
    sup  = result["support_levels"][0]["strike"]  if result["support_levels"]  else "N/A"
    res  = result["resistance_levels"][0]["strike"] if result["resistance_levels"] else "N/A"
    bias = result["bias"]
    skew = result["skew"]["signal"].split("—")[0].strip()

    return (
        f"{sym} multi-strike analysis: PCR {pcr} ({bias}). "
        f"Max pain at ₹{mp} — price tends to pin here near expiry. "
        f"Key support ₹{sup}, resistance ₹{res}. "
        f"Vol skew: {skew}. "
        f"MM expected range ₹{result['mm_range']['lower']}–₹{result['mm_range']['upper']}."
    )


# ═══════════════════════════════════════════════════════════════
# STORAGE
# ═══════════════════════════════════════════════════════════════

def _store_pcr(symbol: str, pcr: float, ce_oi: float, pe_oi: float):
    conn = _conn()
    conn.execute("""
        INSERT INTO pcr_intraday (symbol, pcr, ce_oi, pe_oi, timestamp)
        VALUES (?,?,?,?,?)
    """, (symbol, pcr, ce_oi, pe_oi, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def _save_analysis(symbol: str, expiry: str, spot: float, result: dict):
    conn = _conn()
    conn.execute("""
        INSERT INTO strike_analysis (symbol, expiry, spot, analysis, computed_at)
        VALUES (?,?,?,?,?)
    """, (symbol, expiry, spot, json.dumps(result), result["computed_at"]))
    conn.commit()
    conn.close()


def get_saved_analysis(symbol: str = "NIFTY") -> dict | None:
    conn  = _conn()
    row   = conn.execute(
        "SELECT analysis FROM strike_analysis WHERE symbol=? ORDER BY id DESC LIMIT 1",
        (symbol,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def _conn():
    return sqlite3.connect(DB)
