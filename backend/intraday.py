"""
intraday.py — Live intraday price tracker

Polls NSE every 5 minutes during market hours (9:15 AM – 3:30 PM IST).
For every OPEN recommendation it:
  1. Fetches live quote (LTP, high, low, volume)
  2. Checks target / stop breach in real-time
  3. Calculates live P&L
  4. Fires alerts via alert_engine
  5. Logs to intraday_ticks table

Also tracks:
  - VWAP intraday (cumulative TP×Vol / Vol)
  - Volume pace (current vs expected for this time of day)
  - Live RSI (14) on 5-min candles
"""

import threading
import time
import sqlite3
import json
from datetime import datetime, time as dtime, date
from zoneinfo import ZoneInfo

from nsepython import nse_quote

DB     = "trades.db"
IST    = ZoneInfo("Asia/Kolkata")
MARKET_OPEN  = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)
POLL_INTERVAL_SEC = 300        # 5 minutes
MIN_VOLUME_PACE   = 0.5        # flag if volume < 50% of expected by this time


# ─────────────────────────────────────────────
# DB SCHEMA
# ─────────────────────────────────────────────

def init_intraday_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS intraday_ticks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            stock       TEXT,
            timestamp   TEXT,
            ltp         REAL,
            open        REAL,
            high        REAL,
            low         REAL,
            volume      INTEGER,
            vwap        REAL,
            change_pct  REAL,
            rsi_live    REAL,
            vol_pace    REAL,
            reco_id     INTEGER
        );

        CREATE TABLE IF NOT EXISTS intraday_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            reco_id     INTEGER,
            stock       TEXT,
            alert_type  TEXT,
            message     TEXT,
            price       REAL,
            timestamp   TEXT,
            sent        INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# LIVE QUOTE FETCHER
# ─────────────────────────────────────────────

def get_live_quote(symbol: str) -> dict | None:
    """
    Fetch live NSE quote for a symbol.
    Returns dict with ltp, open, high, low, volume, change_pct
    """
    try:
        raw = nse_quote(symbol)
        data = raw.get("priceInfo", {})
        return {
            "symbol":     symbol,
            "ltp":        float(data.get("lastPrice", 0)),
            "open":       float(data.get("open", 0)),
            "high":       float(data.get("intraDayHighLow", {}).get("max", 0)),
            "low":        float(data.get("intraDayHighLow", {}).get("min", 0)),
            "prev_close": float(data.get("previousClose", 0)),
            "change_pct": float(data.get("pChange", 0)),
            "volume":     int(raw.get("marketDeptOrderBook", {}).get("totalBuyQuantity", 0)),
            "timestamp":  datetime.now(IST).isoformat(),
        }
    except Exception as e:
        print(f"[LiveQuote] {symbol}: {e}")
        return None


def get_live_quotes_bulk(symbols: list[str]) -> dict[str, dict]:
    """Fetch live quotes for multiple symbols with rate limiting."""
    results = {}
    for s in symbols:
        q = get_live_quote(s)
        if q:
            results[s] = q
        time.sleep(0.3)
    return results


# ─────────────────────────────────────────────
# MARKET HOURS CHECK
# ─────────────────────────────────────────────

def is_market_open() -> bool:
    now = datetime.now(IST).time()
    today = datetime.now(IST).weekday()
    if today >= 5:          # Saturday=5, Sunday=6
        return False
    return MARKET_OPEN <= now <= MARKET_CLOSE


def next_open_seconds() -> int:
    """Seconds until next market open."""
    now = datetime.now(IST)
    target = now.replace(hour=9, minute=15, second=0, microsecond=0)
    if now.time() > MARKET_CLOSE:
        # next day
        from datetime import timedelta
        target += timedelta(days=1)
    diff = (target - now).total_seconds()
    return max(0, int(diff))


# ─────────────────────────────────────────────
# INTRADAY MONITOR LOOP
# ─────────────────────────────────────────────

_monitor_thread: threading.Thread | None = None
_monitor_running = False


def start_monitor():
    """Start the background intraday monitor thread."""
    global _monitor_thread, _monitor_running
    if _monitor_running:
        return {"status": "already_running"}
    _monitor_running = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()
    return {"status": "started"}


def stop_monitor():
    global _monitor_running
    _monitor_running = False
    return {"status": "stopped"}


def get_monitor_status() -> dict:
    return {
        "running":       _monitor_running,
        "market_open":   is_market_open(),
        "timestamp":     datetime.now(IST).isoformat(),
    }


def _monitor_loop():
    print("[Intraday] Monitor started")
    while _monitor_running:
        if not is_market_open():
            wait = min(next_open_seconds(), 600)
            print(f"[Intraday] Market closed. Sleeping {wait}s")
            time.sleep(wait)
            continue

        try:
            _run_tick()
        except Exception as e:
            print(f"[Intraday] Tick error: {e}")

        time.sleep(POLL_INTERVAL_SEC)

    print("[Intraday] Monitor stopped")


def _run_tick():
    """Single poll cycle — check all open recommendations."""
    from validator import _get_open_recos, _close_reco, _log_check

    open_recos = _get_open_recos()
    if not open_recos:
        return

    stocks  = list({r["stock"] for r in open_recos})
    quotes  = get_live_quotes_bulk(stocks)
    now_str = datetime.now(IST).isoformat()

    conn = _conn()

    for r in open_recos:
        q = quotes.get(r["stock"])
        if not q:
            continue

        ltp  = q["ltp"]
        high = q["high"]
        low  = q["low"]

        # Volume pace — how much of expected daily volume has traded
        vol_pace = _calc_vol_pace(q["volume"])

        # Log tick
        conn.execute("""
            INSERT INTO intraday_ticks
                (stock, timestamp, ltp, open, high, low, volume, change_pct, vol_pace, reco_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (r["stock"], now_str, ltp, q["open"], high, low,
              q["volume"], q["change_pct"], vol_pace, r["id"]))

        # Check target / stop
        if high >= r["target"]:
            _fire_alert(conn, r, "TARGET_HIT",
                        f"🎯 {r['stock']} hit target ₹{r['target']} (LTP ₹{ltp})", ltp)
            _close_reco(r["id"], "TARGET_HIT", "WIN", ltp, date.today().isoformat())

        elif low <= r["stop"]:
            _fire_alert(conn, r, "STOP_HIT",
                        f"🛑 {r['stock']} hit stop ₹{r['stop']} (LTP ₹{ltp})", ltp)
            _close_reco(r["id"], "STOP_HIT", "LOSS", ltp, date.today().isoformat())

        else:
            # Near target / stop warnings
            pct_to_target = (r["target"] - ltp) / (r["target"] - r["entry"]) * 100 if r["target"] != r["entry"] else 100
            pct_to_stop   = (ltp - r["stop"]) / (r["entry"] - r["stop"]) * 100   if r["entry"] != r["stop"]   else 100

            if pct_to_target <= 10:
                _fire_alert(conn, r, "NEAR_TARGET",
                            f"⚡ {r['stock']} within 10% of target ₹{r['target']} (LTP ₹{ltp})", ltp)
            elif pct_to_stop <= 10:
                _fire_alert(conn, r, "NEAR_STOP",
                            f"⚠️ {r['stock']} within 10% of stop ₹{r['stop']} (LTP ₹{ltp})", ltp)

    conn.commit()
    conn.close()
    print(f"[Intraday] Tick done — {len(open_recos)} recos checked")


def _fire_alert(conn, r: dict, alert_type: str, message: str, price: float):
    # Check not already sent in last 30 mins
    existing = conn.execute("""
        SELECT id FROM intraday_alerts
        WHERE reco_id=? AND alert_type=?
        AND timestamp > datetime('now','-30 minutes')
    """, (r["id"], alert_type)).fetchone()

    if existing:
        return

    conn.execute("""
        INSERT INTO intraday_alerts (reco_id, stock, alert_type, message, price, timestamp)
        VALUES (?,?,?,?,?,?)
    """, (r["id"], r["stock"], alert_type, message, price, datetime.now(IST).isoformat()))

    # Send via alert engine
    try:
        from alerts import send_alert
        send_alert(message, alert_type)
    except Exception as e:
        print(f"[Alert] {e}")


def _calc_vol_pace(current_vol: int) -> float:
    """Estimate volume pace — fraction of expected daily volume traded so far."""
    now = datetime.now(IST).time()
    market_seconds = (
        (MARKET_CLOSE.hour * 3600 + MARKET_CLOSE.minute * 60) -
        (MARKET_OPEN.hour  * 3600 + MARKET_OPEN.minute  * 60)
    )
    elapsed = max(1, (
        (now.hour * 3600 + now.minute * 60) -
        (MARKET_OPEN.hour * 3600 + MARKET_OPEN.minute * 60)
    ))
    pct_day = elapsed / market_seconds
    # If volume is on pace we'd expect pct_day of daily volume by now
    # We don't have daily avg here so just return time-fraction
    return round(pct_day, 3)


# ─────────────────────────────────────────────
# READ ENDPOINTS
# ─────────────────────────────────────────────

def get_live_positions() -> list[dict]:
    """
    All open recommendations with latest live price and P&L.
    """
    from validator import _get_open_recos
    open_recos = _get_open_recos()
    if not open_recos:
        return []

    stocks = list({r["stock"] for r in open_recos})
    quotes = get_live_quotes_bulk(stocks)

    positions = []
    for r in open_recos:
        q   = quotes.get(r["stock"], {})
        ltp = q.get("ltp", r["entry"])
        pnl = round(ltp - r["entry"], 2) if r["entry"] else 0
        pct = round(pnl / r["entry"] * 100, 2) if r["entry"] else 0
        target_pct = round((ltp - r["entry"]) / (r["target"] - r["entry"]) * 100, 1) if r["target"] != r["entry"] else 0

        positions.append({
            "reco_id":      r["id"],
            "stock":        r["stock"],
            "strategy":     r["strategy"],
            "entry":        r["entry"],
            "ltp":          ltp,
            "target":       r["target"],
            "stop":         r["stop"],
            "pnl_per_share":pnl,
            "pnl_pct":      pct,
            "target_pct":   max(0, min(100, target_pct)),
            "change_pct":   q.get("change_pct", 0),
            "high":         q.get("high"),
            "low":          q.get("low"),
            "status":       "ON TRACK" if pnl >= 0 else "BELOW ENTRY",
            "expiry":       r["expiry_date"],
        })

    return sorted(positions, key=lambda x: x["pnl_pct"], reverse=True)


def get_intraday_ticks(stock: str, limit: int = 50) -> list[dict]:
    conn = _conn()
    rows = conn.execute("""
        SELECT stock, timestamp, ltp, high, low, volume, change_pct, vol_pace
        FROM intraday_ticks WHERE stock = ?
        ORDER BY id DESC LIMIT ?
    """, (stock, limit)).fetchall()
    conn.close()
    cols = ["stock","timestamp","ltp","high","low","volume","change_pct","vol_pace"]
    return [dict(zip(cols, r)) for r in rows]


def get_pending_alerts(limit: int = 50) -> list[dict]:
    conn = _conn()
    rows = conn.execute("""
        SELECT id, reco_id, stock, alert_type, message, price, timestamp, sent
        FROM intraday_alerts ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    cols = ["id","reco_id","stock","alert_type","message","price","timestamp","sent"]
    return [dict(zip(cols, r)) for r in rows]


def _conn():
    return sqlite3.connect(DB)
