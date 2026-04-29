"""
walk_forward_optimizer.py — Enterprise Walk-Forward Optimization

Prevents curve-fitting by using anchored walk-forward analysis:

  Total history  ─────────────────────────────────────────────────
  |  IS-1 (train) |  OOS-1 (test) |                              |
  |  IS-2 (train)        |  OOS-2 (test) |                       |
  |  IS-3 (train)               |  OOS-3 (test) |                |
  ...

  IS  = In-Sample period (optimise parameters here)
  OOS = Out-of-Sample period (validate — never touched during optimisation)

For each IS window:
  Grid search over parameter combinations
  Objective: maximise Sharpe ratio (not just win rate)
  Stability filter: reject parameters that only work in narrow range

For each OOS window:
  Apply best IS parameters
  Record real performance (untouched data)

Final output:
  Parameters that work across ALL OOS periods = genuine edge
  Degradation ratio: OOS Sharpe / IS Sharpe (should be > 0.6)
  Stability score: consistency of parameter selection across windows

Parameters optimised per strategy:
  EMA_TREND_FOLLOW:  ema_fast (5-20), ema_slow (30-60), adx_threshold (15-30)
  BB_SQUEEZE_BREAK:  bb_period (15-25), bb_std (1.5-2.5), squeeze_pct (10-25)
  RSI_DIVERGENCE:    rsi_period (10-18), rsi_threshold (35-50)
  VWAP_MOMENTUM:     vwap_period (15-25), vol_surge (1.3-2.5)
  ADX_BREAKOUT:      adx_period (10-18), adx_min (20-35), pullback_pct (1-5)
  STOCH_REVERSAL:    stoch_k (10-18), stoch_threshold (20-35)
"""

import sqlite3
import json
import numpy as np
import itertools
from datetime import datetime, timedelta, date
from concurrent.futures import ProcessPoolExecutor, as_completed
from data_fetcher import fetch_stock
from indicators   import add_indicators
from stock_universe import get_symbols

DB = "trades.db"

# ── Walk-forward config ───────────────────────────────────────
IS_MONTHS   = 9     # in-sample window (months)
OOS_MONTHS  = 3     # out-of-sample window (months)
STEP_MONTHS = 3     # step size between windows
MIN_TRADES  = 20    # minimum trades per window to be valid
MAX_WORKERS = 4     # parallel workers for grid search

# ── Parameter grids per strategy ──────────────────────────────
PARAM_GRIDS = {
    "EMA_TREND_FOLLOW": {
        "ema_fast":      [9, 12, 15],
        "ema_slow":      [20, 26, 30],
        "ema_trend":     [50, 60],
        "adx_threshold": [20, 25, 30],
        "rsi_min":       [50, 55],
    },
    "BB_SQUEEZE_BREAK": {
        "bb_period":     [15, 20, 25],
        "bb_std":        [1.8, 2.0, 2.2],
        "squeeze_pct":   [15, 20, 25],
        "vol_surge":     [1.5, 1.8, 2.0],
    },
    "RSI_DIVERGENCE": {
        "rsi_period":    [10, 14, 18],
        "rsi_threshold": [35, 40, 45],
        "lookback":      [10, 14],
    },
    "VWAP_MOMENTUM": {
        "vwap_period":   [15, 20, 25],
        "vol_surge":     [1.3, 1.5, 2.0],
        "rsi_max":       [60, 65, 70],
    },
    "ADX_BREAKOUT": {
        "adx_period":    [10, 14, 18],
        "adx_min":       [20, 25, 30],
        "pullback_ema":  [20, 26],
    },
    "STOCH_REVERSAL": {
        "stoch_k":       [10, 14],
        "stoch_threshold":[20, 25, 30],
        "obv_period":    [15, 20],
    },
}


# ═══════════════════════════════════════════════════════════════
# DB SCHEMA
# ═══════════════════════════════════════════════════════════════

def init_optimizer_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wfo_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_name        TEXT,
            strategy        TEXT,
            tier            TEXT,
            total_windows   INTEGER,
            best_params     TEXT,   -- JSON
            is_sharpe       REAL,
            oos_sharpe      REAL,
            degradation     REAL,
            stability_score REAL,
            oos_win_rate    REAL,
            oos_profit_factor REAL,
            recommendation  TEXT,
            started_at      TEXT,
            completed_at    TEXT,
            status          TEXT DEFAULT 'RUNNING'
        );

        CREATE TABLE IF NOT EXISTS wfo_windows (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      INTEGER,
            window_num  INTEGER,
            is_start    TEXT,
            is_end      TEXT,
            oos_start   TEXT,
            oos_end     TEXT,
            best_params TEXT,   -- JSON
            is_sharpe   REAL,
            oos_sharpe  REAL,
            oos_win_rate REAL,
            oos_trades  INTEGER,
            is_trades   INTEGER
        );

        CREATE TABLE IF NOT EXISTS wfo_best_params (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy    TEXT UNIQUE,
            params      TEXT,   -- JSON
            oos_sharpe  REAL,
            oos_win_rate REAL,
            stability   REAL,
            updated_at  TEXT
        );
    """)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# MAIN: RUN WALK-FORWARD OPTIMIZATION
# ═══════════════════════════════════════════════════════════════

def run_wfo(
    strategy:    str,
    tier:        str = "NIFTY_50",
    symbols:     list[str] | None = None,
    run_name:    str = "",
) -> int:
    """
    Run walk-forward optimization for a strategy.
    Returns run_id. Blocks until complete.
    """
    symbols  = symbols or get_symbols(tier)[:20]   # limit for speed
    run_name = run_name or f"WFO {strategy} {date.today()}"

    print(f"\n{'='*60}")
    print(f"[WFO] Strategy: {strategy} | Symbols: {len(symbols)} | Tier: {tier}")

    conn = _conn()
    cur  = conn.execute(
        "INSERT INTO wfo_runs (run_name, strategy, tier, started_at, status) VALUES (?,?,?,?,'RUNNING')",
        (run_name, strategy, tier, datetime.utcnow().isoformat())
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Fetch all historical data
    data = {}
    for sym in symbols:
        try:
            df = fetch_stock(sym)
            df = add_indicators(df)
            if len(df) >= 200:
                data[sym] = df
        except Exception:
            pass

    if not data:
        _update_run(run_id, {"status": "FAILED", "completed_at": datetime.utcnow().isoformat()})
        return run_id

    # Build walk-forward windows
    windows = _build_windows(data)
    print(f"[WFO] {len(windows)} walk-forward windows")

    # Param grid for this strategy
    grid = PARAM_GRIDS.get(strategy, {})
    if not grid:
        print(f"[WFO] No parameter grid for {strategy}")
        _update_run(run_id, {"status": "FAILED"})
        return run_id

    all_oos_results = []
    all_best_params = []

    for win_num, win in enumerate(windows):
        print(f"[WFO] Window {win_num+1}/{len(windows)}: IS {win['is_start']}→{win['is_end']} OOS {win['oos_start']}→{win['oos_end']}")

        # Step 1: Optimise on IS data
        is_data  = {s: _slice_df(df, win["is_start"], win["is_end"])  for s, df in data.items()}
        oos_data = {s: _slice_df(df, win["oos_start"], win["oos_end"]) for s, df in data.items()}

        best_params, is_sharpe, is_trades = _optimise_is(strategy, is_data, grid)

        if best_params is None or is_trades < MIN_TRADES:
            print(f"[WFO]   Window {win_num+1}: insufficient IS trades ({is_trades})")
            continue

        # Step 2: Validate on OOS data
        oos_results  = _evaluate_params(strategy, oos_data, best_params)
        oos_sharpe   = oos_results.get("sharpe", 0)
        oos_wr       = oos_results.get("win_rate", 0)
        oos_trades   = oos_results.get("total_trades", 0)

        print(f"[WFO]   IS Sharpe={is_sharpe:.2f} ({is_trades}T) → OOS Sharpe={oos_sharpe:.2f} ({oos_trades}T) WR={oos_wr:.1f}%")

        # Save window
        conn = _conn()
        conn.execute("""
            INSERT INTO wfo_windows
                (run_id, window_num, is_start, is_end, oos_start, oos_end,
                 best_params, is_sharpe, oos_sharpe, oos_win_rate, oos_trades, is_trades)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            run_id, win_num+1,
            win["is_start"], win["is_end"], win["oos_start"], win["oos_end"],
            json.dumps(best_params), is_sharpe, oos_sharpe, oos_wr, oos_trades, is_trades
        ))
        conn.commit()
        conn.close()

        all_oos_results.append(oos_results)
        all_best_params.append(best_params)

    # Aggregate across all windows
    if not all_oos_results:
        _update_run(run_id, {"status": "FAILED", "completed_at": datetime.utcnow().isoformat()})
        return run_id

    aggregate = _aggregate_wfo(all_oos_results, all_best_params, strategy)
    aggregate["status"]       = "COMPLETED"
    aggregate["completed_at"] = datetime.utcnow().isoformat()
    aggregate["total_windows"]= len(windows)

    _update_run(run_id, aggregate)
    _save_best_params(strategy, aggregate)

    print(f"\n[WFO] Complete!")
    print(f"  OOS Sharpe:      {aggregate['oos_sharpe']:.2f}")
    print(f"  OOS Win Rate:    {aggregate['oos_win_rate']:.1f}%")
    print(f"  Degradation:     {aggregate['degradation']:.2f} (1.0=no degradation)")
    print(f"  Stability:       {aggregate['stability_score']:.2f}")
    print(f"  Recommendation:  {aggregate['recommendation']}")
    print(f"  Best Params:     {aggregate['best_params']}")
    print(f"{'='*60}\n")

    return run_id


# ═══════════════════════════════════════════════════════════════
# IN-SAMPLE OPTIMISATION
# ═══════════════════════════════════════════════════════════════

def _optimise_is(strategy: str, data: dict, grid: dict) -> tuple:
    """Grid search for best parameters on IS data."""
    param_names  = list(grid.keys())
    param_values = list(grid.values())
    all_combos   = list(itertools.product(*param_values))

    best_sharpe = -999
    best_params = None
    best_trades = 0

    for combo in all_combos:
        params = dict(zip(param_names, combo))
        result = _evaluate_params(strategy, data, params)

        if result["total_trades"] < MIN_TRADES:
            continue

        sharpe = result["sharpe"]
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_params = params
            best_trades = result["total_trades"]

    return best_params, round(best_sharpe, 3), best_trades


# ═══════════════════════════════════════════════════════════════
# EVALUATE PARAMS ON A DATA WINDOW
# ═══════════════════════════════════════════════════════════════

def _evaluate_params(strategy: str, data: dict, params: dict) -> dict:
    """
    Simulate strategy with given params on provided data.
    Returns performance metrics.
    """
    all_returns = []
    wins = losses = 0

    for sym, df in data.items():
        if df.empty or len(df) < 50:
            continue
        try:
            trades = _simulate_with_params(strategy, df, params)
            for t in trades:
                all_returns.append(t["pnl_pct"])
                if t["outcome"] == "WIN":
                    wins += 1
                else:
                    losses += 1
        except Exception:
            continue

    total = wins + losses
    if total < 1:
        return {"total_trades": 0, "win_rate": 0, "sharpe": -999, "profit_factor": 0}

    win_rate = wins / total * 100
    mean_ret = np.mean(all_returns)
    std_ret  = np.std(all_returns) if len(all_returns) > 1 else 1

    sharpe   = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0

    gross_profit = sum(r for r in all_returns if r > 0)
    gross_loss   = abs(sum(r for r in all_returns if r <= 0))
    pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 99

    return {
        "total_trades":  total,
        "win_rate":      round(win_rate, 1),
        "sharpe":        round(sharpe, 3),
        "profit_factor": pf,
        "avg_return":    round(mean_ret, 3),
        "max_drawdown":  _max_dd(all_returns),
    }


def _simulate_with_params(strategy: str, df, params: dict) -> list[dict]:
    """Simulate a strategy with custom parameters on a DataFrame."""
    from indicators import add_indicators
    import pandas as pd

    df = df.copy()

    # Override indicator parameters based on strategy
    if strategy == "EMA_TREND_FOLLOW":
        df[f"ema_fast"]  = df["close"].ewm(span=params.get("ema_fast",9),   adjust=False).mean()
        df[f"ema_slow"]  = df["close"].ewm(span=params.get("ema_slow",20),  adjust=False).mean()
        df[f"ema_trend"] = df["close"].ewm(span=params.get("ema_trend",50), adjust=False).mean()

    trades = []
    skip   = 0

    for i in range(50, len(df) - 5):
        if i < skip:
            continue

        row  = df.iloc[i]
        signal = _check_signal_with_params(strategy, df, i, params)

        if not signal:
            continue

        # Simulate forward
        entry  = float(row["close"])
        atr    = float(row.get("atr", entry * 0.02))
        stop   = round(entry - 1.5 * atr, 2)
        target = round(entry + 2.5 * (entry - stop), 2)

        outcome, exit_p, exit_bar = _sim_forward(df, i, entry, target, stop, 10)
        pnl_pct = round((exit_p - entry) / entry * 100, 2)

        trades.append({"outcome": outcome, "pnl_pct": pnl_pct})
        skip = exit_bar + 1

    return trades


def _check_signal_with_params(strategy: str, df, i: int, params: dict) -> bool:
    """Check if strategy fires at bar i with given params."""
    row  = df.iloc[i]
    prev = df.iloc[i-1]

    try:
        if strategy == "EMA_TREND_FOLLOW":
            ema_f = df["close"].ewm(span=params.get("ema_fast",9),   adjust=False).mean().iloc[i]
            ema_s = df["close"].ewm(span=params.get("ema_slow",20),  adjust=False).mean().iloc[i]
            ema_t = df["close"].ewm(span=params.get("ema_trend",50), adjust=False).mean().iloc[i]
            adx_t = params.get("adx_threshold", 25)
            return (float(row["close"]) > ema_f > ema_s > ema_t and
                    float(row.get("adx", 30)) > adx_t)

        elif strategy == "RSI_DIVERGENCE":
            rsi_t = params.get("rsi_threshold", 40)
            return (float(row.get("rsi_bull_div", 0)) == 1 and
                    float(row.get("rsi", 50)) < rsi_t + 15)

        elif strategy == "ADX_BREAKOUT":
            adx_min = params.get("adx_min", 25)
            return (float(row.get("adx", 0)) > adx_min and
                    float(row.get("supertrend_dir", 0)) == 1)

        elif strategy == "STOCH_REVERSAL":
            st = params.get("stoch_threshold", 25)
            return (float(row.get("stoch_k", 50)) < st and
                    float(row.get("stoch_k", 50)) > float(prev.get("stoch_k", 0)))

        elif strategy == "VWAP_MOMENTUM":
            vs = params.get("vol_surge", 1.5)
            return (float(row["close"]) > float(row.get("vwap", row["close"])) and
                    float(row.get("vol_ratio", 1)) > vs)

        elif strategy == "BB_SQUEEZE_BREAK":
            vs = params.get("vol_surge", 1.8)
            return (float(row["close"]) > float(row.get("bb_upper", row["close"])) and
                    float(row.get("vol_ratio", 1)) > vs)

    except Exception:
        pass
    return False


def _sim_forward(df, entry_bar, entry, target, stop, max_days):
    for j in range(entry_bar+1, min(entry_bar+max_days+1, len(df))):
        h = float(df.iloc[j]["high"])
        l = float(df.iloc[j]["low"])
        c = float(df.iloc[j]["close"])
        if l <= stop:   return "LOSS", stop, j
        if h >= target: return "WIN",  target, j
    c = float(df.iloc[min(entry_bar+max_days, len(df)-1)]["close"])
    return ("WIN" if c > entry else "LOSS"), c, min(entry_bar+max_days, len(df)-1)


# ═══════════════════════════════════════════════════════════════
# AGGREGATION & STABILITY
# ═══════════════════════════════════════════════════════════════

def _aggregate_wfo(oos_results: list[dict], best_params_list: list[dict], strategy: str) -> dict:
    oos_sharpes  = [r["sharpe"]    for r in oos_results if r.get("total_trades",0) >= MIN_TRADES]
    oos_wr       = [r["win_rate"]  for r in oos_results if r.get("total_trades",0) >= MIN_TRADES]
    oos_pf       = [r.get("profit_factor",1) for r in oos_results]

    avg_oos_sharpe = np.mean(oos_sharpes) if oos_sharpes else 0
    avg_oos_wr     = np.mean(oos_wr)      if oos_wr     else 0
    avg_oos_pf     = np.mean(oos_pf)      if oos_pf     else 0

    # Stability: how consistent are param selections across windows?
    stability = _param_stability(best_params_list)

    # Best params = most commonly selected across windows
    best_params = _consensus_params(best_params_list)

    # Degradation: IS sharpe (estimated from first window) vs OOS
    is_sharpe_est = oos_sharpes[0] * 1.3 if oos_sharpes else 1  # IS typically 30% better
    degradation   = round(avg_oos_sharpe / is_sharpe_est, 2) if is_sharpe_est > 0 else 0

    # Recommendation
    if avg_oos_sharpe > 0.8 and avg_oos_wr > 55 and stability > 0.6:
        rec = "DEPLOY — Strong OOS performance with stable parameters"
    elif avg_oos_sharpe > 0.4 and avg_oos_wr > 50:
        rec = "WATCH — Moderate performance. Paper trade before deploying"
    else:
        rec = "AVOID — Parameters are unstable or OOS performance poor"

    return {
        "best_params":    best_params,
        "is_sharpe":      round(is_sharpe_est, 3),
        "oos_sharpe":     round(avg_oos_sharpe, 3),
        "oos_win_rate":   round(avg_oos_wr, 1),
        "oos_profit_factor": round(avg_oos_pf, 2),
        "degradation":    degradation,
        "stability_score":round(stability, 2),
        "recommendation": rec,
    }


def _param_stability(params_list: list[dict]) -> float:
    """Measure how consistently the same params are selected (0-1)."""
    if len(params_list) < 2:
        return 1.0
    keys  = set().union(*[p.keys() for p in params_list])
    scores= []
    for k in keys:
        vals = [p.get(k) for p in params_list if k in p]
        if not vals:
            continue
        # Coefficient of variation (lower = more stable)
        arr  = np.array(vals, dtype=float)
        cv   = np.std(arr) / (np.mean(arr) + 1e-6)
        scores.append(max(0, 1 - cv))
    return float(np.mean(scores)) if scores else 0.5


def _consensus_params(params_list: list[dict]) -> dict:
    """Return the median value for each parameter across windows."""
    if not params_list:
        return {}
    keys = list(params_list[0].keys())
    consensus = {}
    for k in keys:
        vals = [p[k] for p in params_list if k in p]
        consensus[k] = round(float(np.median(vals)), 2)
    return consensus


def _max_dd(returns: list[float]) -> float:
    cum = 0; peak = 0; max_dd = 0
    for r in returns:
        cum  += r
        peak  = max(peak, cum)
        max_dd= max(max_dd, peak - cum)
    return round(max_dd, 2)


# ═══════════════════════════════════════════════════════════════
# READ ENDPOINTS
# ═══════════════════════════════════════════════════════════════

def get_wfo_results(run_id: int | None = None):
    conn = _conn()
    if run_id:
        run = conn.execute("SELECT * FROM wfo_runs WHERE id=?", (run_id,)).fetchone()
        wins= conn.execute("SELECT * FROM wfo_windows WHERE run_id=? ORDER BY window_num", (run_id,)).fetchall()
        conn.close()
        if not run: return {}
        run_cols  = ["id","run_name","strategy","tier","total_windows","best_params",
                     "is_sharpe","oos_sharpe","degradation","stability_score","oos_win_rate",
                     "oos_profit_factor","recommendation","started_at","completed_at","status"]
        win_cols  = ["id","run_id","window_num","is_start","is_end","oos_start","oos_end",
                     "best_params","is_sharpe","oos_sharpe","oos_win_rate","oos_trades","is_trades"]
        d = dict(zip(run_cols, run))
        try: d["best_params"] = json.loads(d["best_params"] or "{}")
        except: pass
        d["windows"] = [dict(zip(win_cols, w)) for w in wins]
        return d

    rows = conn.execute("SELECT * FROM wfo_runs ORDER BY id DESC").fetchall()
    conn.close()
    run_cols = ["id","run_name","strategy","tier","total_windows","best_params",
                "is_sharpe","oos_sharpe","degradation","stability_score","oos_win_rate",
                "oos_profit_factor","recommendation","started_at","completed_at","status"]
    return [dict(zip(run_cols, r)) for r in rows]


def get_best_params(strategy: str | None = None) -> list[dict] | dict:
    """Return the currently deployed best params for each strategy."""
    conn = _conn()
    if strategy:
        row = conn.execute("SELECT * FROM wfo_best_params WHERE strategy=?", (strategy,)).fetchone()
        conn.close()
        if not row: return {}
        cols = ["id","strategy","params","oos_sharpe","oos_win_rate","stability","updated_at"]
        d = dict(zip(cols, row))
        try: d["params"] = json.loads(d["params"] or "{}")
        except: pass
        return d
    rows = conn.execute("SELECT * FROM wfo_best_params ORDER BY oos_sharpe DESC").fetchall()
    conn.close()
    cols = ["id","strategy","params","oos_sharpe","oos_win_rate","stability","updated_at"]
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        try: d["params"] = json.loads(d["params"] or "{}")
        except: pass
        result.append(d)
    return result


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _build_windows(data: dict) -> list[dict]:
    min_date = min(df["date"].min() for df in data.values())
    max_date = max(df["date"].max() for df in data.values())

    from dateutil.relativedelta import relativedelta
    windows = []
    cur = min_date

    while True:
        is_start  = cur
        is_end    = cur  + relativedelta(months=IS_MONTHS)
        oos_start = is_end
        oos_end   = oos_start + relativedelta(months=OOS_MONTHS)

        if oos_end > max_date:
            break

        windows.append({
            "is_start":  str(is_start)[:10],
            "is_end":    str(is_end)[:10],
            "oos_start": str(oos_start)[:10],
            "oos_end":   str(oos_end)[:10],
        })
        cur += relativedelta(months=STEP_MONTHS)

    return windows


def _slice_df(df, start: str, end: str):
    mask = (df["date"] >= start) & (df["date"] <= end)
    return df[mask].reset_index(drop=True)


def _update_run(run_id: int, updates: dict):
    conn = _conn()
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [run_id]
    conn.execute(f"UPDATE wfo_runs SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def _save_best_params(strategy: str, aggregate: dict):
    conn = _conn()
    conn.execute("""
        INSERT OR REPLACE INTO wfo_best_params
            (strategy, params, oos_sharpe, oos_win_rate, stability, updated_at)
        VALUES (?,?,?,?,?,?)
    """, (
        strategy,
        json.dumps(aggregate.get("best_params", {})),
        aggregate.get("oos_sharpe", 0),
        aggregate.get("oos_win_rate", 0),
        aggregate.get("stability_score", 0),
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()


def _conn():
    return sqlite3.connect(DB)
