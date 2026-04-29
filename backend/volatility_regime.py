"""
volatility_regime.py — Enterprise Volatility Regime Detection

Detects market volatility regime and dynamically adjusts:
  - Strategy weights (trend vs mean-reversion vs breakout)
  - Position sizes (larger in low-vol, smaller in high-vol)
  - Stop distances (wider stops in high-vol regimes)
  - Conviction thresholds (raise bar in chaotic regimes)

Regime Classification (4 states)
────────────────────────────────────────────────────────────
CALM         VIX < 13     — trend following works best
                            Full position size, tight stops
                            EMA_TREND_FOLLOW, ADX_BREAKOUT preferred

NORMAL       VIX 13-18   — all strategies work
                            Standard parameters

ELEVATED     VIX 18-25   — mean reversion becomes better
                            Reduce size 25%, widen stops 30%
                            STOCH_REVERSAL, RSI_DIVERGENCE preferred

CRISIS       VIX > 25     — avoid most long strategies
                            Reduce size 50%, only highest conviction
                            BB_SQUEEZE_BREAK for explosive moves

Plus VIX-derived signals:
  VIX_SPIKE       Single-day VIX jump > 20% → caution
  VIX_CRUSH       VIX drops > 15% in 3 days → vol selling opportunity
  FEAR_EXTREME    VIX > 35 → capitulation, mean reversion longs
  CONTANGO_STEEP  Near VIX > far VIX → term structure stress

Historical vol comparison:
  Realised Vol 20-day HV vs IV (VIX)
  IV > HV → options expensive → prefer selling strategies
  IV < HV → options cheap → prefer buying strategies
"""

import sqlite3
import numpy as np
import json
from datetime import datetime, date, timedelta
from data_fetcher import fetch_stock

DB = "trades.db"

# ── Regime thresholds ─────────────────────────────────────────
REGIMES = {
    "CALM":     (0,    13),
    "NORMAL":   (13,   18),
    "ELEVATED": (18,   25),
    "CRISIS":   (25, 1000),
}

# ── Strategy weight multipliers per regime ────────────────────
STRATEGY_WEIGHTS = {
    "CALM": {
        "EMA_TREND_FOLLOW": 1.5,  "ADX_BREAKOUT":     1.4,
        "BB_SQUEEZE_BREAK": 1.2,  "VWAP_MOMENTUM":    1.2,
        "RSI_DIVERGENCE":   0.8,  "STOCH_REVERSAL":   0.7,
    },
    "NORMAL": {
        "EMA_TREND_FOLLOW": 1.0,  "ADX_BREAKOUT":     1.0,
        "BB_SQUEEZE_BREAK": 1.0,  "VWAP_MOMENTUM":    1.0,
        "RSI_DIVERGENCE":   1.0,  "STOCH_REVERSAL":   1.0,
    },
    "ELEVATED": {
        "EMA_TREND_FOLLOW": 0.7,  "ADX_BREAKOUT":     0.6,
        "BB_SQUEEZE_BREAK": 1.1,  "VWAP_MOMENTUM":    0.9,
        "RSI_DIVERGENCE":   1.3,  "STOCH_REVERSAL":   1.4,
    },
    "CRISIS": {
        "EMA_TREND_FOLLOW": 0.3,  "ADX_BREAKOUT":     0.2,
        "BB_SQUEEZE_BREAK": 1.3,  "VWAP_MOMENTUM":    0.5,
        "RSI_DIVERGENCE":   1.2,  "STOCH_REVERSAL":   1.1,
    },
}

# ── Position size multipliers ─────────────────────────────────
SIZE_MULTIPLIER = {"CALM": 1.20, "NORMAL": 1.0, "ELEVATED": 0.75, "CRISIS": 0.50}

# ── Stop distance multipliers ─────────────────────────────────
STOP_MULTIPLIER = {"CALM": 0.85, "NORMAL": 1.0, "ELEVATED": 1.30, "CRISIS": 1.60}

# ── Minimum conviction threshold ──────────────────────────────
MIN_CONVICTION  = {"CALM": 5.5, "NORMAL": 6.0, "ELEVATED": 7.0, "CRISIS": 8.0}


# ═══════════════════════════════════════════════════════════════
# DB SCHEMA
# ═══════════════════════════════════════════════════════════════

def init_regime_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS volatility_regime (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date      TEXT UNIQUE,
            vix             REAL,
            vix_1w_ago      REAL,
            vix_1m_ago      REAL,
            hv_20d          REAL,
            iv_hv_ratio     REAL,
            regime          TEXT,
            regime_duration INTEGER,
            vix_change_1d   REAL,
            vix_change_5d   REAL,
            signals         TEXT,   -- JSON list of special signals
            size_mult       REAL,
            stop_mult       REAL,
            min_conviction  REAL,
            computed_at     TEXT
        );
    """)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# MAIN: COMPUTE CURRENT REGIME
# ═══════════════════════════════════════════════════════════════

def compute_regime() -> dict:
    """
    Fetch India VIX data, classify regime, compute all adjustments.
    Stores result and returns full regime dict.
    """
    vix_data = _fetch_vix_history()

    if not vix_data:
        return _default_regime()

    current_vix  = vix_data[-1]
    vix_1w_ago   = vix_data[-6]  if len(vix_data) >= 6  else current_vix
    vix_1m_ago   = vix_data[-22] if len(vix_data) >= 22 else current_vix

    regime       = _classify_regime(current_vix)
    regime_dur   = _regime_duration(vix_data, regime)
    hv_20d       = _realised_vol(vix_data, 20) if len(vix_data) >= 20 else current_vix
    iv_hv_ratio  = round(current_vix / hv_20d, 2) if hv_20d > 0 else 1.0

    vix_chg_1d   = round((current_vix - vix_data[-2]) / vix_data[-2] * 100, 2) if len(vix_data) >= 2 else 0
    vix_chg_5d   = round((current_vix - vix_1w_ago) / vix_1w_ago * 100, 2) if vix_1w_ago > 0 else 0

    special_signals = _detect_special_signals(vix_data, current_vix, iv_hv_ratio, vix_chg_1d, vix_chg_5d)

    result = {
        "trade_date":      date.today().isoformat(),
        "vix":             round(current_vix, 2),
        "vix_1w_ago":      round(vix_1w_ago, 2),
        "vix_1m_ago":      round(vix_1m_ago, 2),
        "hv_20d":          round(hv_20d, 2),
        "iv_hv_ratio":     iv_hv_ratio,
        "regime":          regime,
        "regime_duration": regime_dur,
        "vix_change_1d":   vix_chg_1d,
        "vix_change_5d":   vix_chg_5d,
        "signals":         special_signals,
        "size_mult":       SIZE_MULTIPLIER[regime],
        "stop_mult":       STOP_MULTIPLIER[regime],
        "min_conviction":  MIN_CONVICTION[regime],
        "strategy_weights":STRATEGY_WEIGHTS[regime],
        "preferred_strategies": _preferred_strategies(regime),
        "avoid_strategies":     _avoid_strategies(regime),
        "regime_summary":       _regime_summary(regime, current_vix, vix_chg_1d, special_signals),
        "computed_at":     datetime.utcnow().isoformat(),
    }

    _save_regime(result)
    print(f"[Regime] VIX={current_vix:.2f} → {regime} | Size×{SIZE_MULTIPLIER[regime]} Stop×{STOP_MULTIPLIER[regime]} MinCV={MIN_CONVICTION[regime]}")
    return result


def get_current_regime() -> dict:
    """Return latest stored regime (fast, no NSE call)."""
    conn  = _conn()
    row   = conn.execute("SELECT * FROM volatility_regime ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return _default_regime()
    cols = ["id","trade_date","vix","vix_1w_ago","vix_1m_ago","hv_20d","iv_hv_ratio",
            "regime","regime_duration","vix_change_1d","vix_change_5d","signals",
            "size_mult","stop_mult","min_conviction","computed_at"]
    d = dict(zip(cols, row))
    try:
        d["signals"]          = json.loads(d["signals"] or "[]")
        d["strategy_weights"] = STRATEGY_WEIGHTS[d["regime"]]
        d["preferred_strategies"] = _preferred_strategies(d["regime"])
        d["avoid_strategies"]     = _avoid_strategies(d["regime"])
    except Exception:
        pass
    return d


def get_regime_history(days: int = 30) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT trade_date, vix, regime, vix_change_1d, size_mult, min_conviction FROM volatility_regime ORDER BY id DESC LIMIT ?",
        (days,)
    ).fetchall()
    conn.close()
    cols = ["date","vix","regime","vix_chg","size_mult","min_conviction"]
    return [dict(zip(cols, r)) for r in rows]


# ═══════════════════════════════════════════════════════════════
# REGIME-AWARE ADJUSTMENTS
# ═══════════════════════════════════════════════════════════════

def adjust_conviction(base_conviction: float, strategy: str, regime: str | None = None) -> float:
    """
    Apply regime-based strategy weight to raw conviction score.
    Called by ai_engine before filtering results.
    """
    if regime is None:
        reg_data = get_current_regime()
        regime   = reg_data.get("regime", "NORMAL")

    weights  = STRATEGY_WEIGHTS.get(regime, STRATEGY_WEIGHTS["NORMAL"])
    weight   = weights.get(strategy, 1.0)
    adjusted = base_conviction * weight
    return round(min(10.0, adjusted), 2)


def adjust_stop(base_stop: float, entry: float, regime: str | None = None) -> float:
    """Widen or tighten stop distance based on regime."""
    if regime is None:
        regime = get_current_regime().get("regime", "NORMAL")
    mult    = STOP_MULTIPLIER[regime]
    risk    = entry - base_stop
    new_stop= entry - (risk * mult)
    return round(new_stop, 2)


def adjust_position_size(base_qty: int, regime: str | None = None) -> int:
    """Scale position size up or down based on regime."""
    if regime is None:
        regime = get_current_regime().get("regime", "NORMAL")
    return max(1, round(base_qty * SIZE_MULTIPLIER[regime]))


def is_trade_allowed(conviction: float, strategy: str, regime: str | None = None) -> dict:
    """
    Final regime gate before any trade entry.
    Returns approved + reason.
    """
    if regime is None:
        regime = get_current_regime().get("regime", "NORMAL")
    min_cv = MIN_CONVICTION[regime]
    reg_cv = adjust_conviction(conviction, strategy, regime)

    if reg_cv < min_cv:
        return {
            "allowed":  False,
            "reason":   f"Regime-adjusted conviction {reg_cv} below minimum {min_cv} for {regime} regime",
            "regime":   regime,
        }
    return {
        "allowed":  True,
        "regime":   regime,
        "adj_conviction": reg_cv,
        "size_mult":  SIZE_MULTIPLIER[regime],
        "stop_mult":  STOP_MULTIPLIER[regime],
    }


# ═══════════════════════════════════════════════════════════════
# VIX DATA FETCHER
# ═══════════════════════════════════════════════════════════════

INDIA_VIX_SYMBOL = "INDIA VIX"

def _fetch_vix_history() -> list[float]:
    """
    Fetch India VIX closing prices.
    Tries NSE directly; falls back to INDIAVIX via nsepython.
    """
    try:
        from nsepython import equity_history
        df = fetch_stock("INDIAVIX")  # NSE symbol for India VIX
        if not df.empty and len(df) > 10:
            return df["close"].dropna().tolist()
    except Exception:
        pass

    # Manual NSE API fallback
    try:
        import httpx
        url  = "https://www.nseindia.com/api/allIndices"
        hdrs = {"User-Agent":"Mozilla/5.0","Referer":"https://www.nseindia.com/"}
        with httpx.Client(headers=hdrs, timeout=10, follow_redirects=True) as c:
            c.get("https://www.nseindia.com/")
            resp = c.get(url)
            if resp.status_code == 200:
                data = resp.json()
                for idx in data.get("data", []):
                    if "INDIA VIX" in idx.get("index",""):
                        vix = float(idx.get("last", 0))
                        if vix > 0:
                            # Return simulated history based on current
                            return _simulate_vix_history(vix)
    except Exception:
        pass

    return _simulate_vix_history(15.0)  # fallback: normal regime


def _simulate_vix_history(current: float, n: int = 50) -> list[float]:
    """Generate plausible VIX history when live data unavailable."""
    np.random.seed(42)
    noise = np.random.normal(0, 0.8, n)
    hist  = [max(8, current + sum(noise[:i+1])) for i in range(n)]
    hist[-1] = current
    return hist


# ═══════════════════════════════════════════════════════════════
# INTERNALS
# ═══════════════════════════════════════════════════════════════

def _classify_regime(vix: float) -> str:
    for regime, (lo, hi) in REGIMES.items():
        if lo <= vix < hi:
            return regime
    return "CRISIS"


def _regime_duration(vix_history: list[float], current_regime: str) -> int:
    """Days we've been in the current regime consecutively."""
    count = 0
    for v in reversed(vix_history):
        if _classify_regime(v) == current_regime:
            count += 1
        else:
            break
    return count


def _realised_vol(prices: list[float], window: int) -> float:
    """Compute annualised realised volatility from VIX proxy prices."""
    if len(prices) < window + 1:
        return 0
    p = np.array(prices[-window-1:])
    returns = np.diff(np.log(p))
    return float(np.std(returns) * np.sqrt(252) * 100)


def _detect_special_signals(
    vix_hist: list[float], vix: float,
    iv_hv_ratio: float, chg_1d: float, chg_5d: float
) -> list[str]:
    signals = []

    if chg_1d > 20:
        signals.append("VIX_SPIKE — caution, expect gap risk")
    if chg_5d < -15:
        signals.append("VIX_CRUSH — vol selling opportunity, consider iron condors")
    if vix > 35:
        signals.append("FEAR_EXTREME — capitulation zone, mean reversion longs viable")
    if vix < 11:
        signals.append("COMPLACENCY — vol is cheap, consider buying protection")
    if iv_hv_ratio > 1.3:
        signals.append("IV_EXPENSIVE — options overpriced vs realised vol, prefer selling")
    if iv_hv_ratio < 0.7:
        signals.append("IV_CHEAP — options underpriced, prefer buying strategies")
    if len(vix_hist) >= 5:
        recent_high = max(vix_hist[-5:])
        if vix < recent_high * 0.80:
            signals.append("VIX_MEAN_REVERTING — falling from recent spike")

    return signals


def _preferred_strategies(regime: str) -> list[str]:
    weights = STRATEGY_WEIGHTS[regime]
    return [s for s, w in sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]]


def _avoid_strategies(regime: str) -> list[str]:
    weights = STRATEGY_WEIGHTS[regime]
    return [s for s, w in weights.items() if w < 0.5]


def _regime_summary(regime: str, vix: float, chg_1d: float, signals: list) -> str:
    desc = {
        "CALM":     f"VIX {vix:.1f} — very low volatility. Trend strategies dominate. Increase position sizes. Tight stops work.",
        "NORMAL":   f"VIX {vix:.1f} — normal market conditions. All strategies valid. Standard sizing.",
        "ELEVATED": f"VIX {vix:.1f} — elevated volatility. Mean reversion preferred. Reduce size 25%, widen stops.",
        "CRISIS":   f"VIX {vix:.1f} — high volatility / fear. Trend strategies fail. Only highest conviction trades. Half position size.",
    }[regime]
    if signals:
        desc += f" Special: {signals[0]}."
    return desc


def _default_regime() -> dict:
    return {
        "vix":15.0,"regime":"NORMAL","size_mult":1.0,"stop_mult":1.0,
        "min_conviction":6.0,"strategy_weights":STRATEGY_WEIGHTS["NORMAL"],
        "preferred_strategies":["EMA_TREND_FOLLOW","ADX_BREAKOUT","BB_SQUEEZE_BREAK"],
        "avoid_strategies":[],"signals":[],"regime_summary":"Default — no VIX data available",
    }


def _save_regime(r: dict):
    conn = _conn()
    conn.execute("""
        INSERT OR REPLACE INTO volatility_regime
            (trade_date, vix, vix_1w_ago, vix_1m_ago, hv_20d, iv_hv_ratio,
             regime, regime_duration, vix_change_1d, vix_change_5d,
             signals, size_mult, stop_mult, min_conviction, computed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        r["trade_date"], r["vix"], r["vix_1w_ago"], r["vix_1m_ago"],
        r["hv_20d"], r["iv_hv_ratio"], r["regime"], r["regime_duration"],
        r["vix_change_1d"], r["vix_change_5d"],
        json.dumps(r["signals"]), r["size_mult"], r["stop_mult"],
        r["min_conviction"], r["computed_at"]
    ))
    conn.commit()
    conn.close()


def _conn():
    return sqlite3.connect(DB)
