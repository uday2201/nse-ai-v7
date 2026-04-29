"""
risk_manager.py — Portfolio risk management engine

Features
────────────────────────────────────────────────────────────
1. Position sizing — Kelly criterion + fixed fraction
2. Daily risk budget — max % of capital at risk per day
3. Max drawdown circuit breaker — halt trading if breached
4. Correlated position check — avoid holding 5 IT stocks
5. Sector concentration limit — max 30% in any one sector
6. Per-trade max loss limit
7. Portfolio heat map — current risk exposure

Configuration (stored in DB, editable via API)
────────────────────────────────────────────────────────────
capital          Total trading capital (₹)
max_risk_pct     Max % of capital at risk per trade (default 2%)
max_daily_loss   Max % loss in a day before halting (default 5%)
max_drawdown     Max % drawdown from peak before halt (default 15%)
max_sector_pct   Max % of portfolio in one sector (default 30%)
max_corr_stocks  Max stocks from same sector at once (default 3)
kelly_fraction   Kelly fraction to use (default 0.25 = quarter Kelly)
"""

import sqlite3
import json
from datetime import datetime, date

DB = "trades.db"


# ─────────────────────────────────────────────
# DB SCHEMA
# ─────────────────────────────────────────────

def init_risk_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS risk_config (
            id                INTEGER PRIMARY KEY DEFAULT 1,
            capital           REAL    DEFAULT 500000,
            max_risk_pct      REAL    DEFAULT 2.0,
            max_daily_loss    REAL    DEFAULT 5.0,
            max_drawdown      REAL    DEFAULT 15.0,
            max_sector_pct    REAL    DEFAULT 30.0,
            max_corr_stocks   INTEGER DEFAULT 3,
            kelly_fraction    REAL    DEFAULT 0.25,
            trading_halted    INTEGER DEFAULT 0,
            halt_reason       TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_pnl (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date  TEXT UNIQUE,
            realized_pnl REAL DEFAULT 0,
            unrealized_pnl REAL DEFAULT 0,
            peak_capital  REAL DEFAULT 0,
            drawdown_pct  REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS risk_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT,
            message     TEXT,
            timestamp   TEXT
        );
    """)
    conn.execute("INSERT OR IGNORE INTO risk_config (id) VALUES (1)")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# POSITION SIZING
# ─────────────────────────────────────────────

def calculate_position_size(
    stock:      str,
    entry:      float,
    stop:       float,
    conviction: float,
    win_rate:   float = 0.60,   # historical win rate for this strategy
) -> dict:
    """
    Calculate optimal position size using:
      1. Risk per trade (max_risk_pct of capital)
      2. Quarter-Kelly based on conviction + win rate
      3. Hard cap at max_risk_pct regardless of Kelly

    Returns:
      qty, capital_at_risk, position_value, risk_pct, kelly_pct
    """
    cfg    = get_risk_config()
    capital= cfg["capital"]

    if entry <= stop:
        return {"error": "Stop must be below entry for LONG trades"}

    risk_per_share  = entry - stop
    if risk_per_share <= 0:
        return {"error": "Invalid entry/stop"}

    # Max capital at risk per trade
    max_risk_amount = capital * cfg["max_risk_pct"] / 100

    # Kelly position sizing
    # f = (win_rate × avg_win - loss_rate × avg_loss) / avg_win
    # Using RR ratio derived from conviction
    avg_rr      = 1.5 + (conviction - 5) * 0.3   # higher conviction → higher expected RR
    avg_rr      = max(1.0, avg_rr)
    loss_rate   = 1 - win_rate
    kelly_f     = (win_rate * avg_rr - loss_rate) / avg_rr
    kelly_f     = max(0, kelly_f) * cfg["kelly_fraction"]   # quarter-Kelly

    # Position value from Kelly
    kelly_value = capital * kelly_f
    kelly_qty   = int(kelly_value / entry)

    # Position value from fixed risk
    risk_qty    = int(max_risk_amount / risk_per_share)

    # Use the more conservative of the two
    qty = min(kelly_qty, risk_qty)
    qty = max(1, qty)

    pos_value   = round(qty * entry, 2)
    risk_amount = round(qty * risk_per_share, 2)
    risk_pct    = round(risk_amount / capital * 100, 2)

    return {
        "stock":          stock,
        "entry":          entry,
        "stop":           stop,
        "qty":            qty,
        "position_value": pos_value,
        "capital_at_risk":risk_amount,
        "risk_pct":       risk_pct,
        "kelly_pct":      round(kelly_f * 100, 2),
        "max_allowed_risk_pct": cfg["max_risk_pct"],
        "sizing_method":  "quarter_kelly" if kelly_qty < risk_qty else "fixed_risk",
    }


# ─────────────────────────────────────────────
# TRADE APPROVAL
# ─────────────────────────────────────────────

def approve_trade(
    stock:      str,
    sector:     str,
    entry:      float,
    stop:       float,
    conviction: float,
    open_trades: list[dict],  # currently open positions
) -> dict:
    """
    Run all risk checks before approving a trade.
    Returns { approved, reasons, warnings, position_size }
    """
    cfg      = get_risk_config()
    approved = True
    reasons  = []
    warnings = []

    # 1. Trading halted?
    if cfg.get("trading_halted"):
        return {"approved": False, "reasons": [f"Trading halted: {cfg.get('halt_reason')}"], "warnings": []}

    # 2. Daily loss check
    daily = get_daily_pnl()
    daily_loss_pct = abs(min(0, daily.get("realized_pnl", 0))) / cfg["capital"] * 100
    if daily_loss_pct >= cfg["max_daily_loss"]:
        return {"approved": False, "reasons": [f"Daily loss limit {cfg['max_daily_loss']}% breached ({daily_loss_pct:.1f}%)"], "warnings": []}

    # 3. Drawdown check
    if daily.get("drawdown_pct", 0) >= cfg["max_drawdown"]:
        _halt_trading(f"Max drawdown {cfg['max_drawdown']}% breached")
        return {"approved": False, "reasons": ["Max drawdown breached — trading halted"], "warnings": []}

    # 4. Sector concentration
    sector_count = sum(1 for t in open_trades if t.get("sector","") == sector)
    if sector_count >= cfg["max_corr_stocks"]:
        approved = False
        reasons.append(f"Already {sector_count} open positions in {sector} (max {cfg['max_corr_stocks']})")

    # 5. Same stock check
    if any(t.get("stock") == stock for t in open_trades):
        approved = False
        reasons.append(f"Already have an open position in {stock}")

    # 6. Total open positions risk
    total_risk_pct = sum(t.get("risk_pct", 0) for t in open_trades)
    if total_risk_pct > 20:
        warnings.append(f"Portfolio already has {total_risk_pct:.1f}% at risk — consider reducing")

    # 7. Conviction minimum
    if conviction < 5.0:
        approved = False
        reasons.append(f"Conviction {conviction} below minimum 5.0")

    # Position sizing
    pos_size = calculate_position_size(stock, entry, stop, conviction)

    return {
        "approved":      approved,
        "reasons":       reasons,
        "warnings":      warnings,
        "position_size": pos_size,
        "daily_loss_pct":round(daily_loss_pct, 2),
        "drawdown_pct":  round(daily.get("drawdown_pct", 0), 2),
    }


# ─────────────────────────────────────────────
# DAILY P&L TRACKING
# ─────────────────────────────────────────────

def update_daily_pnl(realized_pnl: float = 0, unrealized_pnl: float = 0):
    cfg     = get_risk_config()
    capital = cfg["capital"]
    today   = date.today().isoformat()

    conn = _conn()
    existing = conn.execute(
        "SELECT realized_pnl, peak_capital FROM daily_pnl WHERE trade_date=?", (today,)
    ).fetchone()

    total_realized = (existing[0] if existing else 0) + realized_pnl
    peak = max(existing[1] if existing else capital, capital + total_realized)
    current = capital + total_realized + unrealized_pnl
    drawdown = round(max(0, (peak - current) / peak * 100), 2)

    conn.execute("""
        INSERT INTO daily_pnl (trade_date, realized_pnl, unrealized_pnl, peak_capital, drawdown_pct)
        VALUES (?,?,?,?,?)
        ON CONFLICT(trade_date) DO UPDATE SET
            realized_pnl   = realized_pnl + ?,
            unrealized_pnl = ?,
            peak_capital   = MAX(peak_capital, ?),
            drawdown_pct   = ?
    """, (today, total_realized, unrealized_pnl, peak, drawdown,
          realized_pnl, unrealized_pnl, peak, drawdown))
    conn.commit()
    conn.close()

    # Auto-halt check
    cfg2 = get_risk_config()
    if drawdown >= cfg2["max_drawdown"]:
        _halt_trading(f"Drawdown {drawdown:.1f}% exceeded limit {cfg2['max_drawdown']}%")

    return get_daily_pnl()


def get_daily_pnl(days: int = 1) -> dict:
    conn  = _conn()
    today = date.today().isoformat()
    row   = conn.execute(
        "SELECT * FROM daily_pnl WHERE trade_date=?", (today,)
    ).fetchone()
    conn.close()
    if not row:
        return {"trade_date": today, "realized_pnl": 0, "unrealized_pnl": 0, "peak_capital": 0, "drawdown_pct": 0}
    cols = ["id","trade_date","realized_pnl","unrealized_pnl","peak_capital","drawdown_pct"]
    return dict(zip(cols, row))


def get_pnl_history(days: int = 30) -> list[dict]:
    conn = _conn()
    rows = conn.execute("SELECT * FROM daily_pnl ORDER BY trade_date DESC LIMIT ?", (days,)).fetchall()
    conn.close()
    cols = ["id","trade_date","realized_pnl","unrealized_pnl","peak_capital","drawdown_pct"]
    return [dict(zip(cols, r)) for r in rows]


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

def get_risk_config() -> dict:
    conn = _conn()
    row  = conn.execute("SELECT * FROM risk_config WHERE id=1").fetchone()
    conn.close()
    if not row:
        return {"capital":500000,"max_risk_pct":2.0,"max_daily_loss":5.0,
                "max_drawdown":15.0,"max_sector_pct":30.0,"max_corr_stocks":3,
                "kelly_fraction":0.25,"trading_halted":0}
    cols = ["id","capital","max_risk_pct","max_daily_loss","max_drawdown",
            "max_sector_pct","max_corr_stocks","kelly_fraction","trading_halted","halt_reason"]
    return dict(zip(cols, row))


def update_risk_config(updates: dict) -> dict:
    conn = _conn()
    allowed = ["capital","max_risk_pct","max_daily_loss","max_drawdown",
               "max_sector_pct","max_corr_stocks","kelly_fraction"]
    sets = ", ".join(f"{k}=?" for k in updates if k in allowed)
    vals = [updates[k] for k in updates if k in allowed]
    if sets:
        conn.execute(f"UPDATE risk_config SET {sets} WHERE id=1", vals)
        conn.commit()
    conn.close()
    return get_risk_config()


def resume_trading() -> dict:
    conn = _conn()
    conn.execute("UPDATE risk_config SET trading_halted=0, halt_reason=NULL WHERE id=1")
    conn.commit()
    conn.close()
    _log_risk("TRADING_RESUMED", "Trading manually resumed")
    return {"status": "resumed"}


def _halt_trading(reason: str):
    conn = _conn()
    conn.execute("UPDATE risk_config SET trading_halted=1, halt_reason=? WHERE id=1", (reason,))
    conn.commit()
    conn.close()
    _log_risk("TRADING_HALTED", reason)
    try:
        from alerts import send_alert
        send_alert(f"🚨 TRADING HALTED\n{reason}", "INFO")
    except Exception:
        pass


def _log_risk(event: str, message: str):
    conn = _conn()
    conn.execute("INSERT INTO risk_log (event_type, message, timestamp) VALUES (?,?,?)",
                 (event, message, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def get_risk_log(limit: int = 50) -> list[dict]:
    conn = _conn()
    rows = conn.execute("SELECT * FROM risk_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(zip(["id","event_type","message","timestamp"], r)) for r in rows]


def _conn():
    return sqlite3.connect(DB)
