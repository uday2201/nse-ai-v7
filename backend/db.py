"""
db.py — Enhanced trade journal with analytics
"""

import sqlite3
import json
from datetime import datetime

DB = "trades.db"


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────

def init_db():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock           TEXT    NOT NULL,
            entry           REAL,
            exit            REAL,
            quantity        INTEGER DEFAULT 1,
            pnl             REAL,
            conviction      REAL,
            conviction_grade TEXT,
            components      TEXT,       -- JSON conviction breakdown
            reason          TEXT,       -- analyst note at entry
            trade_type      TEXT DEFAULT 'EQUITY',   -- EQUITY / OPTIONS
            status          TEXT DEFAULT 'OPEN',     -- OPEN / CLOSED
            entry_time      TEXT,
            exit_time       TEXT
        );
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# WRITE
# ─────────────────────────────────────────────

def insert_trade(trade: dict) -> int:
    """
    Expected keys: stock, entry, conviction (dict), reason
    Optional:      quantity, trade_type
    Returns new trade id.
    """
    conviction = trade.get("conviction", {})
    conn = _conn()
    cur = conn.execute("""
        INSERT INTO trades
            (stock, entry, quantity, conviction, conviction_grade,
             components, reason, trade_type, status, entry_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
    """, (
        trade["stock"],
        trade.get("entry"),
        trade.get("quantity", 1),
        conviction.get("total") if isinstance(conviction, dict) else conviction,
        conviction.get("grade")  if isinstance(conviction, dict) else None,
        json.dumps(conviction.get("components", {})) if isinstance(conviction, dict) else "{}",
        trade.get("reason", ""),
        trade.get("trade_type", "EQUITY"),
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    trade_id = cur.lastrowid
    conn.close()
    return trade_id


def close_trade(trade_id: int, exit_price: float) -> dict:
    conn = _conn()
    row = conn.execute(
        "SELECT entry, quantity FROM trades WHERE id = ?", (trade_id,)
    ).fetchone()

    if not row:
        conn.close()
        return {"error": "trade not found"}

    entry, qty = row
    pnl = (exit_price - entry) * qty if entry else 0

    conn.execute("""
        UPDATE trades
        SET exit = ?, pnl = ?, status = 'CLOSED', exit_time = ?
        WHERE id = ?
    """, (exit_price, round(pnl, 2), datetime.utcnow().isoformat(), trade_id))
    conn.commit()
    conn.close()

    return {"trade_id": trade_id, "pnl": round(pnl, 2), "status": "CLOSED"}


# ─────────────────────────────────────────────
# READ
# ─────────────────────────────────────────────

def get_trades(status: str | None = None) -> list[dict]:
    conn = _conn()
    q = "SELECT * FROM trades"
    params = ()
    if status:
        q += " WHERE status = ?"
        params = (status.upper(),)
    q += " ORDER BY id DESC"
    rows = conn.execute(q, params).fetchall()
    cols = [d[0] for d in conn.execute(q, params).description] if False else [
        "id","stock","entry","exit","quantity","pnl","conviction",
        "conviction_grade","components","reason","trade_type","status",
        "entry_time","exit_time"
    ]
    conn.close()
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        try:
            d["components"] = json.loads(d["components"] or "{}")
        except Exception:
            d["components"] = {}
        result.append(d)
    return result


def get_analytics() -> dict:
    """Aggregated journal analytics."""
    conn = _conn()

    # ── closed trades ──
    closed = conn.execute("""
        SELECT stock, conviction_grade, pnl, components, entry_time
        FROM trades WHERE status = 'CLOSED'
    """).fetchall()

    if not closed:
        conn.close()
        return {"message": "No closed trades yet"}

    pnls       = [r[2] for r in closed if r[2] is not None]
    wins       = [p for p in pnls if p > 0]
    losses     = [p for p in pnls if p <= 0]
    win_rate   = round(len(wins) / len(pnls) * 100, 1) if pnls else 0
    avg_win    = round(sum(wins)   / len(wins)   if wins   else 0, 2)
    avg_loss   = round(sum(losses) / len(losses) if losses else 0, 2)
    profit_factor = round(abs(sum(wins) / sum(losses)), 2) if losses and sum(losses) != 0 else None

    # ── by conviction grade ──
    grade_stats: dict[str, dict] = {}
    for _, grade, pnl, _, _ in closed:
        g = grade or "UNKNOWN"
        if g not in grade_stats:
            grade_stats[g] = {"trades": 0, "wins": 0, "pnl": 0}
        grade_stats[g]["trades"] += 1
        if pnl and pnl > 0:
            grade_stats[g]["wins"] += 1
        grade_stats[g]["pnl"] = round(grade_stats[g]["pnl"] + (pnl or 0), 2)

    # ── best / worst signals ──
    signal_pnl: dict[str, float] = {}
    for _, _, pnl, comp_json, _ in closed:
        try:
            components = json.loads(comp_json or "{}")
        except Exception:
            components = {}
        for sig, val in components.items():
            if sig not in signal_pnl:
                signal_pnl[sig] = 0.0
            signal_pnl[sig] = round(signal_pnl[sig] + (pnl or 0), 2)

    best_signal  = max(signal_pnl, key=signal_pnl.get) if signal_pnl else None
    worst_signal = min(signal_pnl, key=signal_pnl.get) if signal_pnl else None

    conn.close()
    return {
        "total_trades":   len(pnls),
        "win_rate":       win_rate,
        "total_pnl":      round(sum(pnls), 2),
        "avg_win":        avg_win,
        "avg_loss":       avg_loss,
        "profit_factor":  profit_factor,
        "by_grade":       grade_stats,
        "signal_pnl":     signal_pnl,
        "best_signal":    best_signal,
        "worst_signal":   worst_signal,
    }


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

def _conn():
    return sqlite3.connect(DB)
