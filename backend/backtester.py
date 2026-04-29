"""
backtester.py — Historical strategy backtester

How it works
────────────────────────────────────────────────────────────
For each stock × strategy:
  1. Walk forward through historical daily bars (no lookahead)
  2. On each bar: check if strategy signal fires using data up to that bar
  3. If signal fires: record entry, then simulate forward bars
  4. At each forward bar: check if target or stop is hit
  5. If neither hit by duration_days: close at market (expiry)
  6. Aggregate: win rate, avg RR, max drawdown, Sharpe, profit factor

Walk-forward ensures no future data leakage.

Usage
────────────────────────────────────────────────────────────
  POST /backtest/run
    { "symbols": ["RELIANCE","TCS"], "strategies": ["EMA_TREND_FOLLOW"],
      "lookback_days": 365, "tier": "NIFTY_50" }

  GET  /backtest/results          all past backtest runs
  GET  /backtest/results/{id}     single run detail + trades
  GET  /backtest/summary          best strategies across all runs
"""

import sqlite3
import json
from datetime import datetime, timedelta
from data_fetcher   import fetch_stock
from indicators     import add_indicators
from strategies     import score_all
from stock_universe import get_symbols

DB = "trades.db"


# ─────────────────────────────────────────────
# DB SCHEMA
# ─────────────────────────────────────────────

def init_backtest_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS backtest_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_name        TEXT,
            tier            TEXT,
            strategies      TEXT,   -- JSON list
            lookback_days   INTEGER,
            symbols_tested  INTEGER,
            total_trades    INTEGER,
            win_rate        REAL,
            avg_rr          REAL,
            profit_factor   REAL,
            max_drawdown    REAL,
            sharpe          REAL,
            total_return    REAL,
            started_at      TEXT,
            completed_at    TEXT,
            status          TEXT DEFAULT 'RUNNING'
        );

        CREATE TABLE IF NOT EXISTS backtest_trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER,
            stock           TEXT,
            strategy        TEXT,
            entry_date      TEXT,
            exit_date       TEXT,
            entry_price     REAL,
            target_price    REAL,
            stop_price      REAL,
            exit_price      REAL,
            rr_offered      REAL,
            rr_achieved     REAL,
            outcome         TEXT,   -- WIN | LOSS | EXPIRED
            hold_days       INTEGER,
            pnl_pct         REAL
        );
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# RUN BACKTEST
# ─────────────────────────────────────────────

def run_backtest(
    symbols:       list[str]  | None = None,
    tier:          str               = "NIFTY_50",
    strategies:    list[str]  | None = None,
    lookback_days: int               = 365,
    run_name:      str               = "",
) -> int:
    """
    Run backtest. Returns run_id.
    Blocks until complete — run in a background thread for large universes.
    """
    if symbols is None:
        symbols = get_symbols(tier)

    now       = datetime.utcnow().isoformat()
    run_name  = run_name or f"Backtest {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

    conn = _conn()
    cur  = conn.execute("""
        INSERT INTO backtest_runs
            (run_name, tier, strategies, lookback_days, started_at, status)
        VALUES (?,?,?,?,?,'RUNNING')
    """, (run_name, tier, json.dumps(strategies or ["ALL"]), lookback_days, now))
    run_id = cur.lastrowid
    conn.commit()
    conn.close()

    all_trades = []
    symbols_done = 0

    for symbol in symbols:
        try:
            trades = _backtest_symbol(symbol, lookback_days, strategies, run_id)
            all_trades.extend(trades)
            symbols_done += 1
            print(f"[Backtest] {symbol}: {len(trades)} trades  ({symbols_done}/{len(symbols)})")
        except Exception as e:
            print(f"[Backtest] {symbol} error: {e}")

    metrics = _calc_metrics(all_trades)

    conn = _conn()
    conn.execute("""
        UPDATE backtest_runs SET
            symbols_tested=?, total_trades=?, win_rate=?, avg_rr=?,
            profit_factor=?, max_drawdown=?, sharpe=?, total_return=?,
            completed_at=?, status='COMPLETED'
        WHERE id=?
    """, (
        symbols_done,
        metrics["total_trades"],
        metrics["win_rate"],
        metrics["avg_rr"],
        metrics["profit_factor"],
        metrics["max_drawdown"],
        metrics["sharpe"],
        metrics["total_return"],
        datetime.utcnow().isoformat(),
        run_id,
    ))
    conn.commit()
    conn.close()

    print(f"\n[Backtest] Run {run_id} complete — {metrics}")
    return run_id


# ─────────────────────────────────────────────
# PER-SYMBOL WALK-FORWARD
# ─────────────────────────────────────────────

def _backtest_symbol(symbol: str, lookback_days: int,
                     filter_strategies: list[str] | None,
                     run_id: int) -> list[dict]:
    """Walk forward through history and simulate all signal fires."""
    df_full = fetch_stock(symbol)
    df_full = add_indicators(df_full)

    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    df_full = df_full[df_full["date"] >= cutoff].reset_index(drop=True)

    if len(df_full) < 60:
        return []

    trades = []
    in_trade = False
    skip_until = 0   # bar index after which we can enter next trade

    for i in range(50, len(df_full) - 5):   # start at 50 to have indicator warmup
        if i < skip_until:
            continue

        bar = df_full.iloc[i]
        df_up_to_now = df_full.iloc[:i+1]

        # Get strategy signals on data UP TO bar i (no lookahead)
        signals = score_all(df_up_to_now, smart_money=None)
        if not signals:
            continue

        for sig in signals:
            strat = sig["strategy"]
            if filter_strategies and "ALL" not in filter_strategies:
                if strat not in filter_strategies:
                    continue

            entry  = sig["entry"]
            target = sig["target"]
            stop   = sig["stop"]
            dur    = sig["duration"]
            rr     = sig["rr"]

            if entry <= 0 or target <= entry or stop >= entry:
                continue

            # Simulate forward bars to find outcome
            outcome, exit_price, exit_bar = _simulate_trade(
                df_full, i, entry, target, stop, dur
            )

            hold_days = exit_bar - i
            pnl_pct   = round((exit_price - entry) / entry * 100, 2)
            risk       = entry - stop
            rr_achieved = round((exit_price - entry) / risk, 2) if risk > 0 else 0

            trade = {
                "run_id":       run_id,
                "stock":        symbol,
                "strategy":     strat,
                "entry_date":   str(df_full.iloc[i]["date"])[:10],
                "exit_date":    str(df_full.iloc[exit_bar]["date"])[:10],
                "entry_price":  entry,
                "target_price": target,
                "stop_price":   stop,
                "exit_price":   exit_price,
                "rr_offered":   rr,
                "rr_achieved":  rr_achieved,
                "outcome":      outcome,
                "hold_days":    hold_days,
                "pnl_pct":      pnl_pct,
            }
            trades.append(trade)

            # Save to DB
            conn = _conn()
            conn.execute("""
                INSERT INTO backtest_trades
                    (run_id, stock, strategy, entry_date, exit_date,
                     entry_price, target_price, stop_price, exit_price,
                     rr_offered, rr_achieved, outcome, hold_days, pnl_pct)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, tuple(trade.values()))
            conn.commit()
            conn.close()

            skip_until = exit_bar + 1
            break   # one trade per signal bar

    return trades


def _simulate_trade(df, entry_bar: int, entry: float, target: float,
                    stop: float, max_days: int) -> tuple[str, float, int]:
    """
    Walk forward from entry_bar and find outcome.
    Returns (outcome, exit_price, exit_bar_index)
    """
    for j in range(entry_bar + 1, min(entry_bar + max_days + 1, len(df))):
        high = float(df.iloc[j]["high"])
        low  = float(df.iloc[j]["low"])
        close= float(df.iloc[j]["close"])

        if low <= stop:
            return "LOSS", stop, j

        if high >= target:
            return "WIN", target, j

    # Expired at close of last bar
    close = float(df.iloc[min(entry_bar + max_days, len(df)-1)]["close"])
    outcome = "WIN" if close > entry else "LOSS"
    return "EXPIRED", close, min(entry_bar + max_days, len(df)-1)


# ─────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────

def _calc_metrics(trades: list[dict]) -> dict:
    if not trades:
        return {k: 0 for k in ["total_trades","win_rate","avg_rr","profit_factor",
                                "max_drawdown","sharpe","total_return"]}

    wins   = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] != "WIN"]
    total  = len(trades)

    win_rate     = round(len(wins) / total * 100, 1)
    avg_rr       = round(sum(t["rr_achieved"] for t in trades) / total, 2)
    total_return = round(sum(t["pnl_pct"] for t in trades), 2)

    gross_profit = sum(t["pnl_pct"] for t in wins)
    gross_loss   = abs(sum(t["pnl_pct"] for t in losses)) or 1
    profit_factor= round(gross_profit / gross_loss, 2)

    # Max drawdown (peak-to-trough on cumulative PnL)
    cum = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cum  += t["pnl_pct"]
        peak  = max(peak, cum)
        dd    = peak - cum
        max_dd = max(max_dd, dd)
    max_drawdown = round(max_dd, 2)

    # Simplified Sharpe (mean / std of returns)
    import statistics
    returns = [t["pnl_pct"] for t in trades]
    try:
        sharpe = round(statistics.mean(returns) / (statistics.stdev(returns) or 1) * (252**0.5), 2)
    except Exception:
        sharpe = 0

    return {
        "total_trades":  total,
        "win_rate":      win_rate,
        "avg_rr":        avg_rr,
        "profit_factor": profit_factor,
        "max_drawdown":  max_drawdown,
        "sharpe":        sharpe,
        "total_return":  total_return,
    }


# ─────────────────────────────────────────────
# READ ENDPOINTS
# ─────────────────────────────────────────────

def get_backtest_results(run_id: int | None = None) -> list[dict] | dict:
    conn = _conn()
    if run_id:
        run = conn.execute("SELECT * FROM backtest_runs WHERE id=?", (run_id,)).fetchone()
        trades = conn.execute(
            "SELECT * FROM backtest_trades WHERE run_id=? ORDER BY entry_date", (run_id,)
        ).fetchall()
        conn.close()
        if not run:
            return {}
        run_cols = ["id","run_name","tier","strategies","lookback_days","symbols_tested",
                    "total_trades","win_rate","avg_rr","profit_factor","max_drawdown",
                    "sharpe","total_return","started_at","completed_at","status"]
        trade_cols = ["id","run_id","stock","strategy","entry_date","exit_date",
                      "entry_price","target_price","stop_price","exit_price",
                      "rr_offered","rr_achieved","outcome","hold_days","pnl_pct"]
        result = dict(zip(run_cols, run))
        try:
            result["strategies"] = json.loads(result["strategies"])
        except Exception:
            pass
        result["trades"] = [dict(zip(trade_cols, t)) for t in trades]
        return result

    rows = conn.execute("SELECT * FROM backtest_runs ORDER BY id DESC").fetchall()
    conn.close()
    run_cols = ["id","run_name","tier","strategies","lookback_days","symbols_tested",
                "total_trades","win_rate","avg_rr","profit_factor","max_drawdown",
                "sharpe","total_return","started_at","completed_at","status"]
    return [dict(zip(run_cols, r)) for r in rows]


def get_backtest_summary() -> dict:
    """Best strategy per metric across all completed runs."""
    conn = _conn()
    rows = conn.execute("""
        SELECT strategy,
               COUNT(*) as total,
               SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) as wins,
               AVG(rr_achieved) as avg_rr,
               AVG(pnl_pct) as avg_pnl,
               AVG(hold_days) as avg_days
        FROM backtest_trades
        GROUP BY strategy
        ORDER BY wins*1.0/COUNT(*) DESC
    """).fetchall()
    conn.close()
    cols = ["strategy","total","wins","avg_rr","avg_pnl","avg_days"]
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        d["win_rate"]  = round(d["wins"] / d["total"] * 100, 1) if d["total"] else 0
        d["avg_rr"]    = round(d["avg_rr"] or 0, 2)
        d["avg_pnl"]   = round(d["avg_pnl"] or 0, 2)
        d["avg_days"]  = round(d["avg_days"] or 0, 1)
        result.append(d)
    return {"by_strategy": result}


def _conn():
    return sqlite3.connect(DB)
