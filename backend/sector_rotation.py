"""
sector_rotation.py — Sector strength and rotation tracker

Tracks 12 NSE sectors:
  IT, Banking, Pharma, Auto, FMCG, Metal, Energy,
  Realty, Infra, Capital Goods, Telecom, Consumer Durables

For each sector computes:
  - Relative Strength vs NIFTY (20-day)
  - Momentum score (rate of change)
  - OI buildup signal from options data
  - Volume surge vs sector average
  - Sector rotation stage (Leading/Weakening/Lagging/Improving)

Uses the classic RRG (Relative Rotation Graph) quadrant model:
  Leading   — RS > 100, Momentum > 100  (OVERWEIGHT)
  Weakening — RS > 100, Momentum < 100  (REDUCE)
  Lagging   — RS < 100, Momentum < 100  (UNDERWEIGHT)
  Improving — RS < 100, Momentum > 100  (ACCUMULATE)
"""

import sqlite3
import json
from datetime import datetime, timedelta
from data_fetcher import fetch_bulk

DB = "trades.db"

# NSE sector ETFs / index proxies (most liquid representative)
SECTOR_SYMBOLS = {
    "IT":               ["TCS","INFY","WIPRO","HCLTECH","TECHM","LTIM","MPHASIS","COFORGE"],
    "BANKING":          ["HDFCBANK","ICICIBANK","SBIN","AXISBANK","KOTAKBANK","INDUSINDBK","BANDHANBNK","FEDERALBNK"],
    "PHARMA":           ["SUNPHARMA","CIPLA","DRREDDY","DIVISLAB","ALKEM","IPCALAB","LUPIN","AUROPHARMA"],
    "AUTO":             ["MARUTI","TATAMOTORS","BAJAJ-AUTO","HEROMOTOCO","EICHERMOT","M&M","TVSMOTOR","ASHOKLEY"],
    "FMCG":             ["HINDUNILVR","ITC","NESTLEIND","BRITANNIA","DABUR","MARICO","EMAMILTD","COLPAL"],
    "METAL":            ["TATASTEEL","HINDALCO","JSWSTEEL","SAIL","NMDC","COALINDIA","MOIL","VEDL"],
    "ENERGY":           ["RELIANCE","ONGC","BPCL","IOC","GAIL","NTPC","POWERGRID","TATAPOWER"],
    "REALTY":           ["DLF","GODREJPROP","OBEROIRLTY","PHOENIXLTD","SOBHA","LODHA","PRESTIGE","BRIGADE"],
    "INFRA":            ["LT","ADANIPORTS","ADANIENT","IRB","NBCC","GMRINFRA","HUDCO","ENGINERSIN"],
    "CAPITAL_GOODS":    ["SIEMENS","ABB","HAVELLS","CUMMINSIND","BEL","HAL","BHEL","THERMAX"],
    "TELECOM":          ["BHARTIARTL","INDUSTOWER","TATACOMM","MTNL","IDEA","RAILTEL"],
    "CONSUMER_DURABLES":["TITAN","VOLTAS","CROMPTON","WHIRLPOOL","BLUESTARCO","VGUARD","HAVELLS","DIXON"],
}

NIFTY_PROXY = ["RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","HINDUNILVR","ITC","SBIN"]


# ─────────────────────────────────────────────
# DB SCHEMA
# ─────────────────────────────────────────────

def init_sector_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sector_scores (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sector          TEXT,
            rs_score        REAL,
            momentum        REAL,
            volume_surge    REAL,
            stage           TEXT,
            signal          TEXT,
            top_stock       TEXT,
            score           REAL,
            computed_at     TEXT
        );
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# MAIN ANALYSIS
# ─────────────────────────────────────────────

def run_sector_analysis() -> list[dict]:
    """
    Compute sector rotation scores for all 12 sectors.
    Returns sorted list — Leading sectors first.
    """
    print("[Sector] Fetching data...")

    # Fetch all sector stocks + nifty proxy
    all_syms = list({s for syms in SECTOR_SYMBOLS.values() for s in syms} | set(NIFTY_PROXY))
    data     = fetch_bulk(all_syms)

    # Compute NIFTY benchmark returns
    nifty_ret = _avg_return(NIFTY_PROXY, data, 20)

    results = []
    for sector, symbols in SECTOR_SYMBOLS.items():
        try:
            result = _analyse_sector(sector, symbols, data, nifty_ret)
            if result:
                _save_sector(result)
                results.append(result)
        except Exception as e:
            print(f"[Sector] {sector} error: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"[Sector] Done — {len(results)} sectors analysed")
    return results


def get_sector_scores(limit: int = 5) -> list[dict]:
    """Latest sector scores from DB."""
    conn = _conn()
    rows = conn.execute("""
        SELECT DISTINCT sector, rs_score, momentum, volume_surge, stage, signal, top_stock, score, computed_at
        FROM sector_scores
        WHERE computed_at = (SELECT MAX(computed_at) FROM sector_scores WHERE sector = s.sector)
        FROM sector_scores s
        ORDER BY score DESC LIMIT ?
    """, (limit,)).fetchall()

    if not rows:
        # fallback: latest batch
        rows = conn.execute("""
            SELECT sector, rs_score, momentum, volume_surge, stage, signal, top_stock, score, computed_at
            FROM sector_scores
            ORDER BY computed_at DESC, score DESC LIMIT ?
        """, (limit * 3,)).fetchall()

    conn.close()
    cols = ["sector","rs_score","momentum","volume_surge","stage","signal","top_stock","score","computed_at"]
    seen = {}
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        if d["sector"] not in seen:
            seen[d["sector"]] = True
            result.append(d)
    return sorted(result, key=lambda x: x["score"], reverse=True)


def get_leading_sectors() -> list[str]:
    """Returns sector names in LEADING or IMPROVING stage."""
    scores = get_sector_scores(limit=12)
    return [s["sector"] for s in scores if s["stage"] in ("LEADING","IMPROVING")]


# ─────────────────────────────────────────────
# INTERNALS
# ─────────────────────────────────────────────

def _analyse_sector(sector: str, symbols: list[str], data: dict, nifty_ret: float) -> dict | None:
    available = [s for s in symbols if s in data and not data[s].empty]
    if len(available) < 2:
        return None

    ret_20d = _avg_return(available, data, 20)
    ret_10d = _avg_return(available, data, 10)
    ret_5d  = _avg_return(available, data, 5)

    # RS vs NIFTY (relative strength over 20 days)
    rs_score = round((ret_20d / nifty_ret * 100) if nifty_ret != 0 else 100, 2)

    # Momentum = RS acceleration (10d vs 20d)
    rs_10d   = round((ret_10d / nifty_ret * 100) if nifty_ret != 0 else 100, 2)
    momentum = round(rs_10d - rs_score + 100, 2)

    # Volume surge vs 20-day average
    vol_surges = []
    for s in available:
        df = data[s]
        if len(df) >= 20:
            vol_ratio = df["volume"].iloc[-1] / (df["volume"].tail(20).mean() or 1)
            vol_surges.append(vol_ratio)
    vol_surge = round(sum(vol_surges) / len(vol_surges) if vol_surges else 1, 2)

    # RRG Quadrant
    stage = _rrg_stage(rs_score, momentum)

    # Signal
    signal = {
        "LEADING":   "OVERWEIGHT — riding momentum",
        "WEAKENING": "REDUCE — momentum fading",
        "LAGGING":   "UNDERWEIGHT — avoid",
        "IMPROVING": "ACCUMULATE — turning around",
    }.get(stage, "NEUTRAL")

    # Best stock in sector (highest 5d return)
    top_stock = max(available, key=lambda s: _stock_return(data[s], 5))

    # Composite score
    score = round(
        (rs_score - 100) * 0.4 +
        (momentum  - 100) * 0.3 +
        (vol_surge - 1)   * 10 * 0.3,
        2
    )

    return {
        "sector":      sector,
        "rs_score":    rs_score,
        "momentum":    momentum,
        "volume_surge":vol_surge,
        "stage":       stage,
        "signal":      signal,
        "top_stock":   top_stock,
        "score":       score,
        "computed_at": datetime.utcnow().isoformat(),
        "symbols":     available,
        "returns": {
            "5d":  round(ret_5d, 2),
            "10d": round(ret_10d, 2),
            "20d": round(ret_20d, 2),
        }
    }


def _avg_return(symbols: list[str], data: dict, days: int) -> float:
    rets = []
    for s in symbols:
        if s not in data or data[s].empty or len(data[s]) < days + 1:
            continue
        df = data[s]
        r  = (df["close"].iloc[-1] - df["close"].iloc[-days]) / df["close"].iloc[-days] * 100
        rets.append(r)
    return sum(rets) / len(rets) if rets else 0


def _stock_return(df, days: int) -> float:
    if len(df) < days + 1:
        return 0
    return (df["close"].iloc[-1] - df["close"].iloc[-days]) / df["close"].iloc[-days] * 100


def _rrg_stage(rs: float, mom: float) -> str:
    if rs >= 100 and mom >= 100:   return "LEADING"
    if rs >= 100 and mom < 100:    return "WEAKENING"
    if rs < 100  and mom < 100:    return "LAGGING"
    return "IMPROVING"


def _save_sector(r: dict):
    conn = _conn()
    conn.execute("""
        INSERT INTO sector_scores
            (sector, rs_score, momentum, volume_surge, stage, signal, top_stock, score, computed_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (r["sector"], r["rs_score"], r["momentum"], r["volume_surge"],
          r["stage"], r["signal"], r["top_stock"], r["score"], r["computed_at"]))
    conn.commit()
    conn.close()


def _conn():
    return sqlite3.connect(DB)
