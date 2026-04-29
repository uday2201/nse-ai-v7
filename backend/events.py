"""
events.py — Earnings calendar + corporate event tracker

Flags stocks with upcoming results, dividends, splits or
F&O expiry within the recommendation's holding window.
Blocks recommendations where holding period overlaps event.
"""

import sqlite3
import json
from datetime import datetime, date, timedelta

try:
    import httpx
    HTTP = True
except ImportError:
    HTTP = False

DB = "trades.db"

NSE_EVENTS_URL = "https://www.nseindia.com/api/event-calendar"
NSE_HEADERS    = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"}

FNO_EXPIRY_DATES_2025 = [
    "2025-01-30","2025-02-27","2025-03-27","2025-04-24",
    "2025-05-29","2025-06-26","2025-07-31","2025-08-28",
    "2025-09-25","2025-10-30","2025-11-27","2025-12-25",
]


def init_event_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS corporate_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            stock       TEXT,
            event_type  TEXT,
            event_date  TEXT,
            description TEXT,
            fetched_at  TEXT
        );
    """)
    conn.commit()
    conn.close()


def check_events_in_window(stock: str, entry_date: str, exit_date: str) -> dict:
    """
    Returns any events for the stock within the holding window.
    Use this to flag or block recommendations.
    """
    conn  = _conn()
    rows  = conn.execute("""
        SELECT event_type, event_date, description FROM corporate_events
        WHERE stock=? AND event_date BETWEEN ? AND ?
        ORDER BY event_date
    """, (stock, entry_date, exit_date)).fetchall()
    conn.close()

    events = [{"type": r[0], "date": r[1], "description": r[2]} for r in rows]

    # Check F&O expiry in window
    expiry_in_window = [d for d in FNO_EXPIRY_DATES_2025 if entry_date <= d <= exit_date]

    risky = any(e["type"] in ("RESULTS","DIVIDEND","SPLIT","BONUS") for e in events)
    risky = risky or bool(expiry_in_window)

    return {
        "stock":            stock,
        "events":           events,
        "fno_expiry_in_window": expiry_in_window,
        "high_risk":        risky,
        "warning":          "⚠️ Corporate event within holding window — elevated risk" if risky else None,
    }


def fetch_events_from_nse(stock: str | None = None) -> list[dict]:
    """Fetch upcoming events from NSE. Falls back to empty list."""
    if not HTTP:
        return []
    try:
        with httpx.Client(headers=NSE_HEADERS, timeout=15, follow_redirects=True) as client:
            client.get("https://www.nseindia.com/")
            params = {}
            if stock:
                params["symbol"] = stock
            resp = client.get(NSE_EVENTS_URL, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return _parse_and_store_events(data)
    except Exception as e:
        print(f"[Events] NSE fetch error: {e}")
    return []


def get_upcoming_events(days: int = 14) -> list[dict]:
    today = date.today().isoformat()
    until = (date.today() + timedelta(days=days)).isoformat()
    conn  = _conn()
    rows  = conn.execute("""
        SELECT stock, event_type, event_date, description FROM corporate_events
        WHERE event_date BETWEEN ? AND ? ORDER BY event_date, stock
    """, (today, until)).fetchall()
    conn.close()
    return [{"stock": r[0], "type": r[1], "date": r[2], "description": r[3]} for r in rows]


def _parse_and_store_events(data: list) -> list[dict]:
    conn    = _conn()
    stored  = []
    now_str = datetime.utcnow().isoformat()
    for item in (data if isinstance(data, list) else []):
        try:
            stock  = item.get("symbol","").upper()
            etype  = item.get("purpose","OTHER").upper()
            edate  = item.get("exDate") or item.get("bCastDate","")
            desc   = item.get("subject", item.get("purpose",""))
            if not stock or not edate:
                continue
            conn.execute("""
                INSERT OR IGNORE INTO corporate_events (stock, event_type, event_date, description, fetched_at)
                VALUES (?,?,?,?,?)
            """, (stock, etype, edate, desc, now_str))
            stored.append({"stock": stock, "type": etype, "date": edate})
        except Exception:
            continue
    conn.commit()
    conn.close()
    return stored


def _conn():
    return sqlite3.connect(DB)
