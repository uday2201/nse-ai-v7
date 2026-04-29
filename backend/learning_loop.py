"""
learning_loop.py — Self-improving weight adjustment system

How it works
────────────────────────────────────────────────────────
1. Every trade entry is stored with its conviction components snapshot.
2. On trade exit (with PnL), outcome is recorded as WIN / LOSS.
3. After every N closed trades a weight-adjust pass runs:
   - Components that fired on winning trades get +boost
   - Components that fired on losing trades get -decay
4. New weights feed back into conviction_engine on next scan.
5. Performance metrics are stored per signal and overall.
"""

import sqlite3
import json
from datetime import datetime

DB = "trades.db"
MIN_TRADES_FOR_ADJUST = 5   # minimum closed trades before re-weighting
BOOST  = 0.08               # weight increase per winning signal
DECAY  = 0.06               # weight decrease per losing signal
MIN_W  = 0.5                # floor to prevent zeroing out a signal
MAX_W  = 4.0                # cap to prevent runaway


# ─────────────────────────────────────────────
# DB SCHEMA (called once at startup)
# ─────────────────────────────────────────────

def init_learning_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signal_weights (
            id        INTEGER PRIMARY KEY,
            updated   TEXT,
            weights   TEXT        -- JSON
        );

        CREATE TABLE IF NOT EXISTS prediction_log (
            id          INTEGER PRIMARY KEY,
            trade_id    INTEGER,
            stock       TEXT,
            predicted   TEXT,       -- BULLISH / NEUTRAL
            conviction  REAL,
            components  TEXT,       -- JSON snapshot
            outcome     TEXT,       -- WIN / LOSS / OPEN
            pnl         REAL,
            created     TEXT,
            closed      TEXT
        );

        CREATE TABLE IF NOT EXISTS signal_stats (
            signal      TEXT PRIMARY KEY,
            wins        INTEGER DEFAULT 0,
            losses      INTEGER DEFAULT 0,
            total_pnl   REAL    DEFAULT 0,
            last_weight REAL    DEFAULT 1.0
        );
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# LOG A PREDICTION AT ENTRY
# ─────────────────────────────────────────────

def log_prediction(trade_id: int, stock: str, conviction: dict, predicted: str):
    conn = _conn()
    conn.execute("""
        INSERT INTO prediction_log
            (trade_id, stock, predicted, conviction, components, outcome, created)
        VALUES (?, ?, ?, ?, ?, 'OPEN', ?)
    """, (
        trade_id,
        stock,
        predicted,
        conviction["total"],
        json.dumps(conviction.get("components", {})),
        _now(),
    ))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# CLOSE A PREDICTION (on exit)
# ─────────────────────────────────────────────

def close_prediction(trade_id: int, pnl: float):
    outcome = "WIN" if pnl > 0 else "LOSS"
    conn = _conn()
    conn.execute("""
        UPDATE prediction_log
        SET outcome = ?, pnl = ?, closed = ?
        WHERE trade_id = ?
    """, (outcome, pnl, _now(), trade_id))
    conn.commit()
    conn.close()

    _update_signal_stats(trade_id, outcome, pnl)
    _maybe_adjust_weights()


# ─────────────────────────────────────────────
# LOAD CURRENT WEIGHTS (for conviction engine)
# ─────────────────────────────────────────────

def get_current_weights() -> dict | None:
    conn = _conn()
    row = conn.execute(
        "SELECT weights FROM signal_weights ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


# ─────────────────────────────────────────────
# PERFORMANCE SUMMARY
# ─────────────────────────────────────────────

def get_performance() -> dict:
    conn = _conn()

    # overall
    rows = conn.execute("""
        SELECT outcome, COUNT(*), COALESCE(SUM(pnl),0)
        FROM prediction_log
        WHERE outcome != 'OPEN'
        GROUP BY outcome
    """).fetchall()

    stats = {"WIN": (0, 0.0), "LOSS": (0, 0.0)}
    for outcome, cnt, pnl in rows:
        stats[outcome] = (cnt, pnl)

    wins, win_pnl  = stats["WIN"]
    loss, loss_pnl = stats["LOSS"]
    total = wins + loss

    # per-signal
    signal_rows = conn.execute(
        "SELECT signal, wins, losses, total_pnl, last_weight FROM signal_stats"
    ).fetchall()

    signals = []
    for sig, w, l, pnl, wt in signal_rows:
        total_sig = w + l
        signals.append({
            "signal":    sig,
            "wins":      w,
            "losses":    l,
            "win_rate":  round(w / total_sig * 100, 1) if total_sig else 0,
            "total_pnl": round(pnl, 2),
            "weight":    round(wt, 3),
        })

    # current weights
    weights = get_current_weights()

    conn.close()
    return {
        "total_trades":  total,
        "wins":          wins,
        "losses":        loss,
        "win_rate":      round(wins / total * 100, 1) if total else 0,
        "total_pnl":     round(win_pnl + loss_pnl, 2),
        "avg_win":       round(win_pnl  / wins  if wins  else 0, 2),
        "avg_loss":      round(loss_pnl / loss  if loss  else 0, 2),
        "signal_stats":  sorted(signals, key=lambda x: x["win_rate"], reverse=True),
        "current_weights": weights,
    }


# ─────────────────────────────────────────────
# INTERNALS
# ─────────────────────────────────────────────

def _update_signal_stats(trade_id: int, outcome: str, pnl: float):
    conn = _conn()
    row = conn.execute(
        "SELECT components FROM prediction_log WHERE trade_id = ?", (trade_id,)
    ).fetchone()

    if not row:
        conn.close()
        return

    components: dict = json.loads(row[0])

    for signal in components:
        if outcome == "WIN":
            conn.execute("""
                INSERT INTO signal_stats (signal, wins, total_pnl)
                VALUES (?, 1, ?)
                ON CONFLICT(signal) DO UPDATE
                SET wins = wins + 1, total_pnl = total_pnl + excluded.total_pnl
            """, (signal, pnl))
        else:
            conn.execute("""
                INSERT INTO signal_stats (signal, losses, total_pnl)
                VALUES (?, 0, ?)
                ON CONFLICT(signal) DO UPDATE
                SET losses = losses + 1, total_pnl = total_pnl + excluded.total_pnl
            """, (signal, pnl))

    conn.commit()
    conn.close()


def _maybe_adjust_weights():
    conn = _conn()
    closed = conn.execute(
        "SELECT COUNT(*) FROM prediction_log WHERE outcome != 'OPEN'"
    ).fetchone()[0]
    conn.close()

    if closed < MIN_TRADES_FOR_ADJUST:
        return
    if closed % MIN_TRADES_FOR_ADJUST != 0:
        return   # only re-weight every N trades

    _adjust_weights()


def _adjust_weights():
    conn = _conn()
    rows = conn.execute(
        "SELECT signal, wins, losses, last_weight FROM signal_stats"
    ).fetchall()
    conn.close()

    if not rows:
        return

    new_weights = {}
    for signal, wins, losses, last_w in rows:
        total = wins + losses
        if total == 0:
            new_weights[signal] = last_w
            continue

        win_rate = wins / total
        # push weight up when win_rate > 0.5, down when below
        delta = (win_rate - 0.5) * 2   # -1 … +1
        adjustment = delta * BOOST if delta > 0 else delta * DECAY
        new_w = max(MIN_W, min(MAX_W, last_w + adjustment))
        new_weights[signal] = round(new_w, 4)

        # persist last_weight
        conn2 = _conn()
        conn2.execute(
            "UPDATE signal_stats SET last_weight = ? WHERE signal = ?",
            (new_w, signal)
        )
        conn2.commit()
        conn2.close()

    # store snapshot
    conn3 = _conn()
    conn3.execute(
        "INSERT INTO signal_weights (updated, weights) VALUES (?, ?)",
        (_now(), json.dumps(new_weights))
    )
    conn3.commit()
    conn3.close()


def _conn():
    return sqlite3.connect(DB)

def _now():
    return datetime.utcnow().isoformat()
