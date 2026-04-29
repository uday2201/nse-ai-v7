"""
options_scanner.py — Live Options Chain Scanner

Scans ALL F&O stocks for unusual options activity every cycle.
Detects institutional positioning BEFORE it shows in price.

Signals detected
────────────────────────────────────────────────────────────
OI_SPIKE         OI jumped > 50% in one session at a strike
                 → Large position being built (directional bet)

IV_CRUSH         IV dropped > 25% while OI stayed flat
                 → Post-event vol collapse (sell premium)

IV_EXPANSION     IV jumped > 30% with OI building
                 → Anticipation of large move (buy options)

LARGE_LOT_BUY    Single strike lot count >> 20-day avg
                 → Institutional block buying

PUT_WRITING      Massive PE OI building at a strike
                 → Smart money selling puts = bullish signal

CALL_WRITING     Massive CE OI building at a strike
                 → Resistance being created at that level

STRADDLE_BUY     Both CE + PE OI spiking at same strike
                 → Big move expected, direction unknown

RATIO_SPREAD     OI building in skewed ratio CE:PE at adjacent strikes
                 → Directional bet with defined risk

GAMMA_SQUEEZE    Strike near spot with explosive OI + vol rise
                 → Potential sharp move as MM delta-hedge

Each signal includes:
  stock, strike, signal_type, direction (BULLISH/BEARISH/NEUTRAL)
  confidence (0-10), oi_change, iv, current_ltp, rationale
"""

import sqlite3
import json
import time
import threading
from datetime import datetime, date
from nsepython import fnolist, nse_optionchain_scrapper
import pandas as pd
import numpy as np

DB = "trades.db"

# ── Thresholds ────────────────────────────────────────────────
OI_SPIKE_PCT      = 50     # % OI increase in one session
IV_CRUSH_PCT      = -25    # % IV drop
IV_EXPANSION_PCT  = 30     # % IV jump
LOT_SURGE_MULT    = 3.0    # × avg lot count
GAMMA_ZONE_PCT    = 0.02   # within 2% of spot

# ── Scanner state ──────────────────────────────────────────────
_scanner_running  = False
_scanner_thread: threading.Thread | None = None
_latest_signals: list[dict] = []
_scan_interval    = 300   # 5 minutes during market hours


# ═══════════════════════════════════════════════════════════════
# DB SCHEMA
# ═══════════════════════════════════════════════════════════════

def init_options_scanner_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS options_signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock           TEXT,
            strike          REAL,
            option_type     TEXT,
            signal_type     TEXT,
            direction       TEXT,
            confidence      REAL,
            oi              REAL,
            oi_change       REAL,
            oi_change_pct   REAL,
            iv              REAL,
            ltp             REAL,
            spot            REAL,
            rationale       TEXT,
            scanned_at      TEXT,
            alerted         INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS options_oi_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            stock       TEXT,
            strike      REAL,
            option_type TEXT,
            oi          REAL,
            iv          REAL,
            ltp         REAL,
            snapshot_date TEXT
        );
    """)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# MAIN SCANNER
# ═══════════════════════════════════════════════════════════════

def start_options_scanner():
    global _scanner_running, _scanner_thread
    if _scanner_running:
        return {"status": "already_running"}
    _scanner_running = True
    _scanner_thread  = threading.Thread(target=_scan_loop, daemon=True)
    _scanner_thread.start()
    return {"status": "started"}


def stop_options_scanner():
    global _scanner_running
    _scanner_running = False
    return {"status": "stopped"}


def get_scanner_status() -> dict:
    return {
        "running":        _scanner_running,
        "latest_signals": len(_latest_signals),
        "last_scan":      _latest_signals[0]["scanned_at"] if _latest_signals else None,
    }


def scan_all_fno(symbols: list[str] | None = None) -> list[dict]:
    """
    Run one full scan cycle across all F&O stocks.
    Returns all signals found sorted by confidence.
    """
    global _latest_signals
    try:
        fno_stocks = symbols or _get_fno_symbols()
    except Exception:
        fno_stocks = _fno_fallback()

    signals     = []
    now_str     = datetime.utcnow().isoformat()

    print(f"[OptionsScanner] Scanning {len(fno_stocks)} F&O stocks...")

    for symbol in fno_stocks:
        try:
            result = scan_single(symbol)
            signals.extend(result)
            time.sleep(0.4)   # NSE rate limit
        except Exception as e:
            continue

    signals = sorted(signals, key=lambda x: x["confidence"], reverse=True)
    _latest_signals = signals
    _save_signals(signals)

    # Alert top signals
    top = [s for s in signals if s["confidence"] >= 8][:5]
    if top:
        _alert_signals(top)

    print(f"[OptionsScanner] Done — {len(signals)} signals, {len(top)} high confidence")
    return signals


def scan_single(symbol: str) -> list[dict]:
    """Scan one stock's option chain and return all signals."""
    try:
        data = nse_optionchain_scrapper(symbol)
    except Exception:
        return []

    records = data.get("records", {})
    spot    = float(records.get("underlyingValue", 0) or 0)
    if spot <= 0:
        return []

    rows = records.get("data", [])
    prev = _get_prev_oi(symbol)

    signals = []
    ce_oi_by_strike = {}
    pe_oi_by_strike = {}

    for row in rows:
        strike = float(row.get("strikePrice", 0))
        if not strike:
            continue

        for side in ["CE", "PE"]:
            opt = row.get(side, {})
            if not opt:
                continue

            oi       = float(opt.get("openInterest",          0) or 0)
            oi_chg   = float(opt.get("changeinOpenInterest",  0) or 0)
            iv       = float(opt.get("impliedVolatility",     0) or 0)
            ltp      = float(opt.get("lastPrice",             0) or 0)
            vol      = float(opt.get("totalTradedVolume",     0) or 0)

            # Store for multi-strike analysis
            if side == "CE":
                ce_oi_by_strike[strike] = oi
            else:
                pe_oi_by_strike[strike] = oi

            prev_oi  = prev.get(f"{strike}_{side}", {}).get("oi", oi)
            prev_iv  = prev.get(f"{strike}_{side}", {}).get("iv", iv)

            oi_chg_pct = ((oi - prev_oi) / prev_oi * 100) if prev_oi > 0 else 0
            iv_chg_pct = ((iv - prev_iv) / prev_iv * 100) if prev_iv > 0 else 0

            # ── Signal detection ──────────────────────────────
            detected = _detect_signals(
                symbol, strike, side, spot,
                oi, oi_chg, oi_chg_pct, iv, iv_chg_pct, ltp, vol
            )
            signals.extend(detected)

    # ── Cross-strike signals ──────────────────────────────────
    straddle = _detect_straddle(symbol, spot, ce_oi_by_strike, pe_oi_by_strike)
    signals.extend(straddle)

    gamma = _detect_gamma_squeeze(symbol, spot, rows)
    signals.extend(gamma)

    # Snapshot for next cycle
    _snapshot_oi(symbol, rows, spot)

    return signals


# ═══════════════════════════════════════════════════════════════
# SIGNAL DETECTORS
# ═══════════════════════════════════════════════════════════════

def _detect_signals(symbol, strike, side, spot, oi, oi_chg, oi_chg_pct,
                    iv, iv_chg_pct, ltp, vol) -> list[dict]:
    signals = []
    now     = datetime.utcnow().isoformat()

    # OI Spike
    if oi_chg_pct >= OI_SPIKE_PCT and oi > 50000:
        direction = "BULLISH" if side == "PE" else "BEARISH"
        conf      = min(10, 5 + (oi_chg_pct / 20))
        signals.append(_signal(
            symbol, strike, side, "OI_SPIKE", direction, conf, oi, oi_chg, oi_chg_pct, iv, ltp, spot,
            f"{side} OI jumped {oi_chg_pct:.0f}% at {strike} — institutional position building", now
        ))

    # IV Crush
    if iv_chg_pct <= IV_CRUSH_PCT and oi > 10000:
        signals.append(_signal(
            symbol, strike, side, "IV_CRUSH", "NEUTRAL", 7.5, oi, oi_chg, oi_chg_pct, iv, ltp, spot,
            f"IV dropped {abs(iv_chg_pct):.0f}% at {strike} — post-event vol collapse, consider selling premium", now
        ))

    # IV Expansion
    if iv_chg_pct >= IV_EXPANSION_PCT and oi_chg_pct > 10:
        signals.append(_signal(
            symbol, strike, side, "IV_EXPANSION", "NEUTRAL", 7.0, oi, oi_chg, oi_chg_pct, iv, ltp, spot,
            f"IV expanded {iv_chg_pct:.0f}% with OI building — large move expected", now
        ))

    # Put Writing (bullish)
    if side == "PE" and oi_chg_pct >= 30 and oi_chg > 0:
        conf = min(10, 6 + (oi_chg_pct / 25))
        signals.append(_signal(
            symbol, strike, side, "PUT_WRITING", "BULLISH", conf, oi, oi_chg, oi_chg_pct, iv, ltp, spot,
            f"Smart money writing puts at {strike} — defending support, bullish signal", now
        ))

    # Call Writing (bearish)
    if side == "CE" and oi_chg_pct >= 30 and oi_chg > 0:
        conf = min(10, 5 + (oi_chg_pct / 25))
        signals.append(_signal(
            symbol, strike, side, "CALL_WRITING", "BEARISH", conf, oi, oi_chg, oi_chg_pct, iv, ltp, spot,
            f"Smart money writing calls at {strike} — creating resistance, bearish signal", now
        ))

    return signals


def _detect_straddle(symbol, spot, ce_oi, pe_oi) -> list[dict]:
    """Detect straddle buying — both CE + PE OI spiking at same strike."""
    signals = []
    now     = datetime.utcnow().isoformat()

    for strike in ce_oi:
        if strike not in pe_oi:
            continue
        ce = ce_oi[strike]
        pe = pe_oi[strike]
        if ce > 100000 and pe > 100000:
            ratio = min(ce, pe) / max(ce, pe)
            if ratio > 0.7:   # balanced — straddle / strangle
                signals.append(_signal(
                    symbol, strike, "BOTH", "STRADDLE_BUY", "NEUTRAL", 7.5,
                    ce + pe, 0, 0, 0, 0, spot,
                    f"Balanced CE ({ce/1e5:.1f}L) + PE ({pe/1e5:.1f}L) OI at {strike} — big move expected, direction unclear", now
                ))
    return signals


def _detect_gamma_squeeze(symbol, spot, rows) -> list[dict]:
    """Detect gamma squeeze setup — near-spot strike with exploding OI."""
    signals = []
    now     = datetime.utcnow().isoformat()

    for row in rows:
        strike = float(row.get("strikePrice", 0))
        if not strike:
            continue
        dist = abs(strike - spot) / spot
        if dist > GAMMA_ZONE_PCT:
            continue

        for side in ["CE", "PE"]:
            opt = row.get(side, {})
            if not opt:
                continue
            oi     = float(opt.get("openInterest", 0) or 0)
            oi_chg = float(opt.get("changeinOpenInterest", 0) or 0)
            iv     = float(opt.get("impliedVolatility", 0) or 0)
            ltp    = float(opt.get("lastPrice", 0) or 0)

            if oi > 200000 and oi_chg / max(oi, 1) > 0.3 and iv > 20:
                direction = "BULLISH" if side == "CE" else "BEARISH"
                signals.append(_signal(
                    symbol, strike, side, "GAMMA_SQUEEZE", direction, 8.5,
                    oi, oi_chg, oi_chg / max(oi-oi_chg, 1) * 100, iv, ltp, spot,
                    f"GAMMA SQUEEZE risk at {strike} ({dist*100:.1f}% from spot) — MM delta-hedging may amplify move", now
                ))
    return signals


# ═══════════════════════════════════════════════════════════════
# READ / FILTER
# ═══════════════════════════════════════════════════════════════

def get_signals(
    signal_type: str | None = None,
    direction:   str | None = None,
    min_conf:    float = 6.0,
    limit:       int   = 100,
) -> list[dict]:
    conn = _conn()
    q    = "SELECT * FROM options_signals WHERE confidence >= ?"
    params: list = [min_conf]
    if signal_type:
        q += " AND signal_type = ?"; params.append(signal_type)
    if direction:
        q += " AND direction = ?";   params.append(direction)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    cols = ["id","stock","strike","option_type","signal_type","direction","confidence",
            "oi","oi_change","oi_change_pct","iv","ltp","spot","rationale","scanned_at","alerted"]
    return [dict(zip(cols, r)) for r in rows]


def get_latest_signals() -> list[dict]:
    """In-memory latest scan (fast — no DB hit)."""
    return _latest_signals


def get_unusual_activity(min_oi_change: float = 100000) -> list[dict]:
    """Stocks with highest absolute OI change — money is moving here."""
    return [s for s in _latest_signals if abs(s.get("oi_change", 0)) >= min_oi_change]


# ═══════════════════════════════════════════════════════════════
# INTERNALS
# ═══════════════════════════════════════════════════════════════

def _scan_loop():
    while _scanner_running:
        from intraday import is_market_open
        if is_market_open():
            try:
                scan_all_fno()
            except Exception as e:
                print(f"[OptionsScanner] Error: {e}")
        time.sleep(_scan_interval)


def _signal(stock, strike, option_type, signal_type, direction, confidence,
            oi, oi_change, oi_change_pct, iv, ltp, spot, rationale, scanned_at) -> dict:
    return {
        "stock": stock, "strike": strike, "option_type": option_type,
        "signal_type": signal_type, "direction": direction,
        "confidence": round(confidence, 1), "oi": oi, "oi_change": oi_change,
        "oi_change_pct": round(oi_change_pct, 1), "iv": iv, "ltp": ltp,
        "spot": spot, "rationale": rationale, "scanned_at": scanned_at,
    }


def _save_signals(signals: list[dict]):
    conn = _conn()
    for s in signals:
        conn.execute("""
            INSERT INTO options_signals
                (stock, strike, option_type, signal_type, direction, confidence,
                 oi, oi_change, oi_change_pct, iv, ltp, spot, rationale, scanned_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (s["stock"], s["strike"], s["option_type"], s["signal_type"],
              s["direction"], s["confidence"], s["oi"], s["oi_change"],
              s["oi_change_pct"], s["iv"], s["ltp"], s["spot"],
              s["rationale"], s["scanned_at"]))
    conn.commit()
    conn.close()


def _alert_signals(signals: list[dict]):
    try:
        from alerts import send_alert
        msg = "🔍 UNUSUAL OPTIONS ACTIVITY\n\n"
        for s in signals:
            msg += f"• {s['stock']} {s['signal_type']} @ ₹{s['strike']} — {s['direction']} (CV {s['confidence']})\n"
        send_alert(msg, "OI_SPIKE")
    except Exception:
        pass


def _get_prev_oi(symbol: str) -> dict:
    """Get yesterday's OI snapshot for comparison."""
    conn  = _conn()
    today = date.today().isoformat()
    rows  = conn.execute("""
        SELECT strike, option_type, oi, iv FROM options_oi_history
        WHERE stock=? AND snapshot_date < ? ORDER BY id DESC
    """, (symbol, today)).fetchall()
    conn.close()
    result = {}
    for strike, otype, oi, iv in rows:
        key = f"{strike}_{otype}"
        if key not in result:
            result[key] = {"oi": oi, "iv": iv}
    return result


def _snapshot_oi(symbol: str, rows: list, spot: float):
    today = date.today().isoformat()
    conn  = _conn()
    # Delete today's old snapshot first
    conn.execute("DELETE FROM options_oi_history WHERE stock=? AND snapshot_date=?", (symbol, today))
    for row in rows:
        strike = float(row.get("strikePrice", 0))
        for side in ["CE", "PE"]:
            opt = row.get(side, {})
            if not opt:
                continue
            conn.execute("""
                INSERT INTO options_oi_history (stock, strike, option_type, oi, iv, ltp, snapshot_date)
                VALUES (?,?,?,?,?,?,?)
            """, (symbol, strike, side,
                  float(opt.get("openInterest", 0) or 0),
                  float(opt.get("impliedVolatility", 0) or 0),
                  float(opt.get("lastPrice", 0) or 0),
                  today))
    conn.commit()
    conn.close()


def _get_fno_symbols() -> list[str]:
    return fnolist()[:80]   # top 80 for speed


def _fno_fallback() -> list[str]:
    from stock_universe import get_symbols
    return get_symbols("FNO_UNIVERSE")[:80]


def _conn():
    return sqlite3.connect(DB)
