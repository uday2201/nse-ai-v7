"""
validator.py — Automated recommendation validator

Runs daily (or on-demand via /validate endpoint).
For every OPEN recommendation it:
  1. Fetches today's OHLC for the stock
  2. Checks if HIGH >= target  → TARGET_HIT (WIN)
         if LOW  <= stop   → STOP_HIT   (LOSS)
         if today >= expiry → EXPIRED
  3. Updates the recommendation record
  4. Writes a validation_log entry
  5. Updates per-strategy accuracy stats

Validation accuracy table
──────────────────────────────────────────────────────────
/accuracy endpoint returns per-strategy:
  win_rate, avg_rr_achieved, avg_days_to_target
  plus overall system win_rate
"""

import sqlite3
import json
from datetime import datetime, date

from data_fetcher import fetch_stock

DB = "trades.db"


# ─────────────────────────────────────────────
# MAIN VALIDATOR — call this daily
# ─────────────────────────────────────────────

def run_validation() -> dict:
    """
    Check all OPEN recommendations against live prices.
    Returns summary of what changed.
    """
    open_recos = _get_open_recos()
    if not open_recos:
        return {"checked": 0, "closed": 0, "still_open": 0}

    # group by stock to avoid duplicate fetches
    stock_map: dict[str, list] = {}
    for r in open_recos:
        stock_map.setdefault(r["stock"], []).append(r)

    results = {"checked": 0, "target_hit": 0, "stop_hit": 0, "expired": 0, "still_open": 0}

    for symbol, recos in stock_map.items():
        try:
            df = fetch_stock(symbol)
            if df.empty:
                continue
            today_row = df.iloc[-1]
        except Exception:
            continue

        high  = float(today_row["high"])
        low   = float(today_row["low"])
        close = float(today_row["close"])
        today = date.today().isoformat()

        for r in recos:
            results["checked"] += 1
            outcome = _evaluate(r, high, low, close, today)

            _update_max_min(r["id"], high, low)
            _log_check(r["id"], r["stock"], today, close, high, low, outcome["status"], outcome["note"])

            if outcome["closed"]:
                _close_reco(r["id"], outcome["status"], outcome["outcome"], close, today)
                results[outcome["key"]] = results.get(outcome["key"], 0) + 1
            else:
                _touch_checked(r["id"], today)
                results["still_open"] += 1

    return results


def validate_one(reco_id: int) -> dict:
    """Validate a single recommendation on demand."""
    conn = _conn()
    row  = conn.execute("SELECT * FROM recommendations WHERE id = ?", (reco_id,)).fetchone()
    conn.close()
    if not row:
        return {"error": "not found"}

    cols = _cols()
    r    = dict(zip(cols, row))
    try:
        df    = fetch_stock(r["stock"])
        today_row = df.iloc[-1]
    except Exception as e:
        return {"error": str(e)}

    high  = float(today_row["high"])
    low   = float(today_row["low"])
    close = float(today_row["close"])
    today = date.today().isoformat()

    outcome = _evaluate(r, high, low, close, today)
    _update_max_min(reco_id, high, low)
    _log_check(reco_id, r["stock"], today, close, high, low, outcome["status"], outcome["note"])

    if outcome["closed"]:
        _close_reco(reco_id, outcome["status"], outcome["outcome"], close, today)

    return {**r, **outcome}


# ─────────────────────────────────────────────
# ACCURACY ANALYTICS
# ─────────────────────────────────────────────

def get_accuracy() -> dict:
    """
    Per-strategy accuracy report + overall system accuracy.
    """
    conn  = _conn()
    rows  = conn.execute("""
        SELECT strategy, outcome, rr,
               entry, exit_price, target, stop,
               created_at, exit_date, duration_days
        FROM recommendations
        WHERE outcome != 'OPEN'
    """).fetchall()
    conn.close()

    if not rows:
        return {"message": "No completed recommendations yet", "total": 0}

    # ── aggregate ──
    overall       = {"WIN": 0, "LOSS": 0, "EXPIRED": 0}
    per_strategy: dict[str, dict] = {}

    for strategy, outcome, rr, entry, exit_p, target, stop, created, exit_d, dur in rows:
        overall[outcome] = overall.get(outcome, 0) + 1

        if strategy not in per_strategy:
            per_strategy[strategy] = {
                "strategy": strategy,
                "total": 0, "wins": 0, "losses": 0, "expired": 0,
                "win_rate": 0,
                "avg_rr_offered": [],
                "avg_rr_achieved": [],
                "avg_days_to_close": [],
                "total_edge": 0.0,
            }

        s = per_strategy[strategy]
        s["total"] += 1

        if outcome == "WIN":
            s["wins"] += 1
            if entry and exit_p and entry > 0:
                achieved_rr = round((exit_p - entry) / (entry - stop), 2) if stop else rr
                s["avg_rr_achieved"].append(achieved_rr)
        elif outcome == "LOSS":
            s["losses"] += 1
        else:
            s["expired"] += 1

        if rr:
            s["avg_rr_offered"].append(rr)

        if created and exit_d:
            try:
                d1 = datetime.fromisoformat(created).date()
                d2 = datetime.fromisoformat(exit_d).date()
                s["avg_days_to_close"].append((d2 - d1).days)
            except Exception:
                pass

    # ── finalise per-strategy ──
    strategy_list = []
    for s in per_strategy.values():
        total = s["total"]
        s["win_rate"]           = round(s["wins"] / total * 100, 1) if total else 0
        s["avg_rr_offered"]     = round(sum(s["avg_rr_offered"])     / len(s["avg_rr_offered"]),     2) if s["avg_rr_offered"]     else 0
        s["avg_rr_achieved"]    = round(sum(s["avg_rr_achieved"])    / len(s["avg_rr_achieved"]),    2) if s["avg_rr_achieved"]    else 0
        s["avg_days_to_close"]  = round(sum(s["avg_days_to_close"])  / len(s["avg_days_to_close"]),  1) if s["avg_days_to_close"]  else 0
        # edge = (win_rate × avg_rr) − (1 − win_rate) — Kelly-style simplified edge
        wr = s["win_rate"] / 100
        s["edge_score"] = round(wr * s["avg_rr_offered"] - (1 - wr), 3)
        strategy_list.append(s)

    strategy_list.sort(key=lambda x: x["win_rate"], reverse=True)

    total    = sum(overall.values())
    wins     = overall.get("WIN", 0)
    win_rate = round(wins / total * 100, 1) if total else 0

    return {
        "total_recommendations": total,
        "overall": {
            "wins":     wins,
            "losses":   overall.get("LOSS", 0),
            "expired":  overall.get("EXPIRED", 0),
            "win_rate": win_rate,
        },
        "by_strategy": strategy_list,
        "best_strategy":  strategy_list[0]["strategy"]  if strategy_list else None,
        "worst_strategy": strategy_list[-1]["strategy"] if strategy_list else None,
    }


def get_validation_log(reco_id: int | None = None, limit: int = 100) -> list[dict]:
    """Raw validation check log."""
    conn = _conn()
    if reco_id:
        rows = conn.execute(
            "SELECT * FROM validation_log WHERE reco_id = ? ORDER BY id DESC LIMIT ?",
            (reco_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM validation_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    cols = ["id","reco_id","stock","check_date","price","high","low","status","note"]
    return [dict(zip(cols, r)) for r in rows]


# ─────────────────────────────────────────────
# CORE EVALUATION LOGIC
# ─────────────────────────────────────────────

def _evaluate(r: dict, high: float, low: float, close: float, today: str) -> dict:
    target  = r["target"]
    stop    = r["stop"]
    expiry  = r["expiry_date"]

    # Priority: stop always checked first (conservative)
    if low <= stop:
        return {
            "closed":  True,
            "status":  "STOP_HIT",
            "outcome": "LOSS",
            "key":     "stop_hit",
            "note":    f"Low {low} hit stop {stop}",
        }

    if high >= target:
        return {
            "closed":  True,
            "status":  "TARGET_HIT",
            "outcome": "WIN",
            "key":     "target_hit",
            "note":    f"High {high} hit target {target}",
        }

    if today >= expiry:
        outcome = "WIN" if close > r["entry"] else "LOSS"
        return {
            "closed":  True,
            "status":  "EXPIRED",
            "outcome": outcome,
            "key":     "expired",
            "note":    f"Expired. Close {close} vs entry {r['entry']}",
        }

    pct_to_target = round((target - close) / (target - r["entry"]) * 100, 1) if target != r["entry"] else 0
    return {
        "closed":        False,
        "status":        "OPEN",
        "outcome":       "OPEN",
        "key":           "still_open",
        "note":          f"Open. Price {close}. {pct_to_target}% remaining to target.",
        "pct_to_target": pct_to_target,
    }


# ─────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────

def _get_open_recos() -> list[dict]:
    conn = _conn()
    rows = conn.execute("SELECT * FROM recommendations WHERE status = 'OPEN'").fetchall()
    conn.close()
    cols = _cols()
    return [dict(zip(cols, r)) for r in rows]


def _close_reco(reco_id: int, status: str, outcome: str, exit_price: float, exit_date: str):
    conn = _conn()
    conn.execute("""
        UPDATE recommendations
        SET status = ?, outcome = ?, exit_price = ?, exit_date = ?, last_checked = ?
        WHERE id = ?
    """, (status, outcome, exit_price, exit_date, datetime.utcnow().isoformat(), reco_id))
    conn.commit()
    conn.close()


def _update_max_min(reco_id: int, high: float, low: float):
    conn = _conn()
    conn.execute("""
        UPDATE recommendations
        SET max_price = MAX(COALESCE(max_price, 0), ?),
            min_price = MIN(COALESCE(min_price, 9999999), ?)
        WHERE id = ?
    """, (high, low, reco_id))
    conn.commit()
    conn.close()


def _log_check(reco_id, stock, check_date, price, high, low, status, note):
    conn = _conn()
    conn.execute("""
        INSERT INTO validation_log (reco_id, stock, check_date, price, high, low, status, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (reco_id, stock, check_date, price, high, low, status, note))
    conn.commit()
    conn.close()


def _touch_checked(reco_id: int, today: str):
    conn = _conn()
    conn.execute(
        "UPDATE recommendations SET last_checked = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), reco_id)
    )
    conn.commit()
    conn.close()


def _conn():
    return sqlite3.connect(DB)

def _cols():
    return [
        "id","stock","strategy","direction","entry","target","stop","rr",
        "duration_days","expiry_date","conviction","reasons","status","outcome",
        "exit_price","exit_date","max_price","min_price","created_at","last_checked"
    ]
