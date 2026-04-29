"""
main.py — FastAPI v6.0 Enterprise — Complete NSE AI Trading System

NEW ENDPOINTS — Enterprise Features
──────────────────────────────────────────────────────────────
GREEKS
  POST /greeks/compute              single option Greeks
  POST /greeks/iv                   solve implied volatility
  POST /greeks/chain                full option chain Greeks
  POST /greeks/iv-surface           build IV smile/surface
  POST /greeks/pnl-matrix           P&L scenario matrix (strategy legs)
  POST /greeks/portfolio            aggregate portfolio Greeks
  POST /greeks/position-size-delta  size by target delta
  GET  /greeks/portfolio/history    stored portfolio Greeks snapshots

VOLATILITY REGIME
  POST /regime/compute              fetch VIX + classify regime
  GET  /regime/current              latest stored regime
  GET  /regime/history              last N days
  POST /regime/adjust-conviction    apply regime to a conviction score
  POST /regime/is-trade-allowed     regime gate before entry

WALK-FORWARD OPTIMIZATION
  POST /wfo/run                     start WFO for a strategy
  GET  /wfo/results                 all WFO runs
  GET  /wfo/results/{id}            single run + all windows
  GET  /wfo/best-params             currently deployed best params
  GET  /wfo/best-params/{strategy}  params for one strategy

SCHEDULER
  POST /scheduler/start             start autonomous scheduler
  POST /scheduler/stop              stop scheduler
  GET  /scheduler/status            running state + all job status
  POST /scheduler/job/{id}/pause    pause a specific job
  POST /scheduler/job/{id}/resume   resume a specific job
  POST /scheduler/job/{id}/run-now  trigger job immediately
  GET  /scheduler/log               job execution history

ALL PREVIOUS ENDPOINTS PRESERVED (v5.0 compatible)
"""

import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

# ── Core ──────────────────────────────────────────────────────────
from ai_engine          import run_ai_model, run_smart_money, run_levels, run_insights, get_scan_status, DEFAULT_TIER
from recommendation_engine import init_reco_table, generate_recommendations, get_recommendations, get_reco_by_id
from validator          import run_validation, validate_one, get_accuracy, get_validation_log
from db                 import init_db, insert_trade, close_trade, get_trades, get_analytics
from learning_loop      import init_learning_tables, log_prediction, close_prediction, get_performance
from stock_universe     import get_symbols

# ── Phase 1 ───────────────────────────────────────────────────────
from intraday           import init_intraday_tables, start_monitor, stop_monitor, get_monitor_status, get_live_positions, get_live_quote, get_intraday_ticks, get_pending_alerts
from alerts             import init_alert_tables, test_telegram, get_alert_config, update_alert_config, get_alert_log
from backtester         import init_backtest_tables, run_backtest, get_backtest_results, get_backtest_summary
from fii_dii            import init_fii_tables, fetch_and_store, get_latest, get_history, get_signals, get_flow_bias

# ── Phase 2 ───────────────────────────────────────────────────────
from sector_rotation    import init_sector_tables, run_sector_analysis, get_sector_scores, get_leading_sectors
from options_strategy   import init_options_tables, suggest_options_strategy, get_saved_strategies
from risk_manager       import init_risk_tables, get_risk_config, update_risk_config, approve_trade, calculate_position_size, get_daily_pnl, get_pnl_history, resume_trading, get_risk_log
from events             import init_event_tables, check_events_in_window, fetch_events_from_nse, get_upcoming_events

# ── Phase 3 ───────────────────────────────────────────────────────
from advanced_features  import (
    check_multi_timeframe,
    init_watchlist_tables, create_watchlist, add_to_watchlist, remove_from_watchlist, get_watchlists, scan_watchlist,
    init_sentiment_tables, analyse_sentiment, store_sentiment, get_stock_sentiment,
    init_paper_tables, paper_enter, paper_validate, get_paper_portfolio, get_paper_trades,
)

# ── Enterprise ────────────────────────────────────────────────────
from greeks_engine       import (
    init_greeks_tables, compute_greeks, compute_iv, compute_chain_greeks,
    build_iv_surface, pnl_scenario_matrix, aggregate_portfolio_greeks, size_by_delta, hedge_ratio
)
from volatility_regime   import (
    init_regime_tables, compute_regime, get_current_regime,
    get_regime_history, adjust_conviction, is_trade_allowed
)
from walk_forward_optimizer import (
    init_optimizer_tables, run_wfo, get_wfo_results, get_best_params
)
from scheduler           import (
    init_scheduler_tables, start_scheduler, stop_scheduler,
    get_scheduler_status, pause_job, resume_job, run_job_now, get_scheduler_log
)

app = FastAPI(title="NSE AI Trading System", description="Enterprise-grade NSE trading platform", version="6.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Init ALL tables
for fn in [
    init_db, init_learning_tables, init_reco_table, init_intraday_tables,
    init_alert_tables, init_backtest_tables, init_fii_tables, init_sector_tables,
    init_options_tables, init_risk_tables, init_event_tables, init_watchlist_tables,
    init_sentiment_tables, init_paper_tables, init_greeks_tables, init_regime_tables,
    init_optimizer_tables, init_scheduler_tables,
]:
    fn()

_last_results: list[dict] = []
_scan_running: bool = False
VALID_TIERS = ["NIFTY_50","NIFTY_100","NIFTY_200","FNO_UNIVERSE","NIFTY_500","ALL_NSE"]


# ── Models ────────────────────────────────────────────────────────
class TradeIn(BaseModel):
    stock: str; entry: float; quantity: int=1
    conviction: Optional[dict]=None; reason: Optional[str]=""
class CloseIn(BaseModel): exit_price: float
class AlertConfigIn(BaseModel):
    telegram: Optional[int]=None; whatsapp: Optional[int]=None
    email: Optional[int]=None; min_grade: Optional[str]=None
class BacktestIn(BaseModel):
    symbols: Optional[List[str]]=None; tier: str="NIFTY_50"
    strategies: Optional[List[str]]=None; lookback_days: int=365; run_name: str=""
class RiskConfigIn(BaseModel):
    capital: Optional[float]=None; max_risk_pct: Optional[float]=None
    max_daily_loss: Optional[float]=None; max_drawdown: Optional[float]=None
    max_corr_stocks: Optional[int]=None; kelly_fraction: Optional[float]=None
class ApproveTradeIn(BaseModel):
    stock: str; sector: str; entry: float; stop: float
    conviction: float; open_trades: List[dict]=[]
class PositionSizeIn(BaseModel):
    stock: str; entry: float; stop: float; conviction: float; win_rate: float=0.60
class OptionsStrategyIn(BaseModel):
    stock: str; spot_price: float; conviction: float
    bias: str; pcr: float; strategy_signal: str=""
class WatchlistIn(BaseModel): name: str; description: str=""
class WatchlistAddIn(BaseModel): stocks: List[str]; notes: str=""
class SentimentIn(BaseModel): text: str
class SentimentStoreIn(BaseModel): stock: str; headline: str; source: str="NSE"
class PaperEnterIn(BaseModel): reco: dict

# ── Greeks models ─────────────────────────────────────────────────
class GreeksIn(BaseModel):
    spot: float; strike: float; expiry_date: str
    option_type: str; iv: float; r: float=0.065
class IVIn(BaseModel):
    market_price: float; spot: float; strike: float
    expiry_date: str; option_type: str
class PnLMatrixIn(BaseModel):
    legs: List[dict]; spot: float; expiry_date: str
class PortfolioGreeksIn(BaseModel): positions: List[dict]
class DeltaSizeIn(BaseModel):
    target_delta: float; option_delta: float; spot: float; lot_size: int=50
class HedgeRatioIn(BaseModel):
    stock_qty: int; stock_price: float; option_delta: float; lot_size: int=50
class AdjustConvictionIn(BaseModel):
    conviction: float; strategy: str; regime: Optional[str]=None
class TradeAllowedIn(BaseModel):
    conviction: float; strategy: str; regime: Optional[str]=None

# ── WFO model ─────────────────────────────────────────────────────
class WFOIn(BaseModel):
    strategy: str; tier: str="NIFTY_50"
    symbols: Optional[List[str]]=None; run_name: str=""


# ─────────────────────────────────────────────
# SYSTEM
# ─────────────────────────────────────────────
@app.get("/", tags=["System"])
def home():
    regime = get_current_regime()
    return {
        "status":"running","version":"6.0.0",
        "features":["greeks","volatility_regime","walk_forward_optimization","apscheduler",
                    "intraday","alerts","backtesting","fii_dii","sector_rotation",
                    "options_strategy","risk_management","event_calendar",
                    "multi_timeframe","watchlist","sentiment","paper_trading"],
        "current_regime": regime.get("regime","UNKNOWN"),
        "vix":            regime.get("vix"),
        "scheduler_running": get_scheduler_status().get("running", False),
        "scan_running":  _scan_running,
    }


# ─────────────────────────────────────────────
# GREEKS
# ─────────────────────────────────────────────
@app.post("/greeks/compute", tags=["Greeks"])
def greeks_compute(body: GreeksIn):
    """Compute full Greeks for a single option (Delta, Gamma, Theta, Vega, Rho, Vanna, Charm)."""
    return compute_greeks(body.spot, body.strike, body.expiry_date, body.option_type, body.iv, body.r)

@app.post("/greeks/iv", tags=["Greeks"])
def greeks_iv(body: IVIn):
    """Solve implied volatility from market price using Brent's method."""
    return compute_iv(body.market_price, body.spot, body.strike, body.expiry_date, body.option_type)

@app.post("/greeks/pnl-matrix", tags=["Greeks"])
def greeks_pnl_matrix(body: PnLMatrixIn):
    """P&L scenario matrix across ±20% price moves and 4 time slices."""
    return pnl_scenario_matrix(body.legs, body.spot, body.expiry_date)

@app.post("/greeks/portfolio", tags=["Greeks"])
def greeks_portfolio(body: PortfolioGreeksIn):
    """Aggregate Greeks across all options positions. Returns net + dollar Greeks."""
    return aggregate_portfolio_greeks(body.positions)

@app.post("/greeks/position-size-delta", tags=["Greeks"])
def greeks_delta_size(body: DeltaSizeIn):
    """Calculate lots needed to achieve a target portfolio delta."""
    return size_by_delta(body.target_delta, body.option_delta, body.spot, lot_size=body.lot_size)

@app.post("/greeks/hedge-ratio", tags=["Greeks"])
def greeks_hedge(body: HedgeRatioIn):
    """Calculate option contracts needed to delta-hedge a stock position."""
    return hedge_ratio(body.stock_qty, body.stock_price, body.option_delta, body.lot_size)


# ─────────────────────────────────────────────
# VOLATILITY REGIME
# ─────────────────────────────────────────────
@app.post("/regime/compute", tags=["Volatility Regime"])
def regime_compute():
    """Fetch India VIX, classify regime (CALM/NORMAL/ELEVATED/CRISIS), compute all adjustments."""
    return compute_regime()

@app.get("/regime/current", tags=["Volatility Regime"])
def regime_current():
    """Latest stored regime with strategy weights, size/stop multipliers, special signals."""
    return get_current_regime()

@app.get("/regime/history", tags=["Volatility Regime"])
def regime_history(days: int = 30):
    return get_regime_history(days)

@app.post("/regime/adjust-conviction", tags=["Volatility Regime"])
def regime_adjust(body: AdjustConvictionIn):
    """Apply regime-based strategy weight to a conviction score."""
    return {"original": body.conviction, "adjusted": adjust_conviction(body.conviction, body.strategy, body.regime), "strategy": body.strategy}

@app.post("/regime/is-trade-allowed", tags=["Volatility Regime"])
def regime_gate(body: TradeAllowedIn):
    """Regime gate — returns approved + size/stop multipliers for this market environment."""
    return is_trade_allowed(body.conviction, body.strategy, body.regime)


# ─────────────────────────────────────────────
# WALK-FORWARD OPTIMIZATION
# ─────────────────────────────────────────────
@app.post("/wfo/run", tags=["Walk-Forward Optimization"])
def wfo_run(body: WFOIn, background_tasks: BackgroundTasks):
    """
    Start walk-forward optimization for a strategy.
    Runs in background. Check /wfo/results for completion.
    """
    def _bg(): run_wfo(body.strategy, body.tier, body.symbols, body.run_name)
    background_tasks.add_task(_bg)
    return {"status":"started","strategy":body.strategy,"tier":body.tier,
            "message":"WFO running in background. Check /wfo/results."}

@app.get("/wfo/results", tags=["Walk-Forward Optimization"])
def wfo_results(): return get_wfo_results()

@app.get("/wfo/results/{run_id}", tags=["Walk-Forward Optimization"])
def wfo_detail(run_id: int):
    r = get_wfo_results(run_id)
    if not r: raise HTTPException(404,"Not found")
    return r

@app.get("/wfo/best-params", tags=["Walk-Forward Optimization"])
def wfo_best(): return get_best_params()

@app.get("/wfo/best-params/{strategy}", tags=["Walk-Forward Optimization"])
def wfo_best_strategy(strategy: str): return get_best_params(strategy)


# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────
@app.post("/scheduler/start", tags=["Scheduler"])
def scheduler_start():
    """Start the autonomous scheduler. Runs all jobs on their cron schedule."""
    return start_scheduler()

@app.post("/scheduler/stop", tags=["Scheduler"])
def scheduler_stop():
    return stop_scheduler()

@app.get("/scheduler/status", tags=["Scheduler"])
def scheduler_status():
    """Full scheduler state: running jobs, next run times, 7-day success rate."""
    return get_scheduler_status()

@app.post("/scheduler/job/{job_id}/pause", tags=["Scheduler"])
def scheduler_pause(job_id: str): return pause_job(job_id)

@app.post("/scheduler/job/{job_id}/resume", tags=["Scheduler"])
def scheduler_resume(job_id: str): return resume_job(job_id)

@app.post("/scheduler/job/{job_id}/run-now", tags=["Scheduler"])
def scheduler_run_now(job_id: str):
    """Trigger any scheduled job immediately without waiting for next cron time."""
    return run_job_now(job_id)

@app.get("/scheduler/log", tags=["Scheduler"])
def scheduler_log_ep(job_id: Optional[str]=None, limit: int=50):
    return get_scheduler_log(job_id, limit)


# ── ALL V5 ENDPOINTS BELOW (preserved) ────────────────────────────

@app.get("/scan/tiers", tags=["Scan"])
def scan_tiers():
    return [{"tier":t,"symbols":len(get_symbols(t)),"est_seconds":max(5,round(len(get_symbols(t))*0.17)),"recommended":t=="FNO_UNIVERSE"} for t in VALID_TIERS]

@app.post("/scan/run", tags=["Scan"])
def scan_run(background_tasks: BackgroundTasks, tier: str=Query(default=DEFAULT_TIER)):
    global _scan_running
    if _scan_running: return {"status":"already_running"}
    if tier not in VALID_TIERS: raise HTTPException(400,"Invalid tier")
    def _bg():
        global _last_results, _scan_running
        _scan_running=True
        try: _last_results=run_ai_model(tier)
        finally: _scan_running=False
    background_tasks.add_task(_bg)
    return {"status":"started","tier":tier}

@app.get("/scan/progress",tags=["Scan"])
def scan_progress(): return {**get_scan_status(),"scan_active":_scan_running,"results_ready":len(_last_results)}

@app.get("/predictions",tags=["Analysis"])
def predictions(tier:str=Query(default=None)):
    if tier:
        if tier not in VALID_TIERS: raise HTTPException(400,"Invalid tier")
        return run_ai_model(tier)
    return _last_results or run_ai_model("NIFTY_50")

@app.get("/high-conviction",tags=["Analysis"])
def high_conviction(tier:str=Query(default=None)):
    base=run_ai_model(tier) if tier else (_last_results or run_ai_model("NIFTY_50"))
    return [r for r in base if r.get("grade")=="HIGH"]

@app.get("/insights",tags=["Analysis"])
def insights(tier:str=Query(default="NIFTY_50")): return run_insights(tier)

@app.get("/smart-money",tags=["Options"]) 
def smart_money(): return run_smart_money()

@app.get("/levels",tags=["Options"]) 
def levels(): return run_levels()

@app.get("/sectors",tags=["Sector Rotation"]) 
def sectors(): return get_sector_scores(12)

@app.post("/sectors/analyse",tags=["Sector Rotation"])
def sectors_analyse(bg:BackgroundTasks):
    bg.add_task(run_sector_analysis); return {"status":"started"}

@app.get("/sectors/leading",tags=["Sector Rotation"])
def sectors_leading(): return {"leading":get_leading_sectors()}

@app.post("/options/strategy",tags=["Options Strategy"])
def options_strategy_ep(body:OptionsStrategyIn):
    return suggest_options_strategy(body.stock,body.spot_price,body.conviction,body.bias,body.pcr,body.strategy_signal)

@app.get("/options/strategies",tags=["Options Strategy"])
def saved_strategies(stock:Optional[str]=None,limit:int=50): return get_saved_strategies(stock,limit)

@app.get("/risk/config",tags=["Risk"]) 
def risk_config(): return get_risk_config()

@app.put("/risk/config",tags=["Risk"])
def risk_config_update(body:RiskConfigIn): return update_risk_config(body.dict(exclude_none=True))

@app.post("/risk/approve",tags=["Risk"])
def risk_approve(body:ApproveTradeIn): return approve_trade(body.stock,body.sector,body.entry,body.stop,body.conviction,body.open_trades)

@app.post("/risk/position-size",tags=["Risk"])
def position_size(body:PositionSizeIn): return calculate_position_size(body.stock,body.entry,body.stop,body.conviction,body.win_rate)

@app.get("/risk/daily-pnl",tags=["Risk"]) 
def daily_pnl(): return get_daily_pnl()

@app.get("/risk/pnl-history",tags=["Risk"])
def pnl_history(days:int=30): return get_pnl_history(days)

@app.post("/risk/resume",tags=["Risk"]) 
def risk_resume(): return resume_trading()

@app.get("/risk/log",tags=["Risk"])
def risk_log(limit:int=50): return get_risk_log(limit)

@app.get("/events/upcoming",tags=["Events"])
def events_upcoming(days:int=14): return get_upcoming_events(days)

@app.get("/events/check/{stock}",tags=["Events"])
def events_check(stock:str,entry_date:str,exit_date:str): return check_events_in_window(stock.upper(),entry_date,exit_date)

@app.post("/events/fetch",tags=["Events"])
def events_fetch(stock:Optional[str]=None): return {"fetched":fetch_events_from_nse(stock)}

@app.get("/mtf/{symbol}",tags=["Multi-Timeframe"])
def mtf(symbol:str): return check_multi_timeframe(symbol.upper())

@app.get("/watchlists",tags=["Watchlist"]) 
def watchlists(): return get_watchlists()

@app.post("/watchlists",tags=["Watchlist"])
def create_wl(body:WatchlistIn): return create_watchlist(body.name,body.description)

@app.post("/watchlists/{wl_id}/add",tags=["Watchlist"])
def wl_add(wl_id:int,body:WatchlistAddIn): return add_to_watchlist(wl_id,body.stocks,body.notes)

@app.delete("/watchlists/{wl_id}/{stock}",tags=["Watchlist"])
def wl_remove(wl_id:int,stock:str): return remove_from_watchlist(wl_id,stock)

@app.get("/watchlists/{wl_id}/scan",tags=["Watchlist"])
def wl_scan(wl_id:int): return scan_watchlist(wl_id,_last_results or [])

@app.post("/sentiment/analyse",tags=["Sentiment"])
def sentiment_analyse(body:SentimentIn): return analyse_sentiment(body.text)

@app.post("/sentiment/store",tags=["Sentiment"])
def sentiment_store(body:SentimentStoreIn): return store_sentiment(body.stock,body.headline,body.source)

@app.get("/sentiment/{stock}",tags=["Sentiment"])
def sentiment_get(stock:str,days:int=7): return get_stock_sentiment(stock.upper(),days)

@app.get("/paper/portfolio",tags=["Paper Trading"]) 
def paper_portfolio(): return get_paper_portfolio()

@app.get("/paper/trades",tags=["Paper Trading"])
def paper_trades(status:Optional[str]=None): return get_paper_trades(status)

@app.post("/paper/enter",tags=["Paper Trading"])
def paper_enter_ep(body:PaperEnterIn): return paper_enter(body.reco)

@app.post("/paper/validate",tags=["Paper Trading"]) 
def paper_validate_ep(): return paper_validate()

@app.post("/recommendations/generate",tags=["Recommendations"]) 
def generate(): return generate_recommendations()

@app.get("/recommendations",tags=["Recommendations"])
def list_recos(status:Optional[str]=None): return get_recommendations(status)

@app.get("/recommendations/open",tags=["Recommendations"]) 
def open_recos(): return get_recommendations("OPEN")

@app.get("/recommendations/{reco_id}",tags=["Recommendations"])
def reco_detail(reco_id:int):
    r=get_reco_by_id(reco_id)
    if not r: raise HTTPException(404,"Not found")
    return {**r,"validation_log":get_validation_log(reco_id=reco_id)}

@app.get("/validate",tags=["Validation"]) 
def validate_all(): return run_validation()

@app.get("/validate/{reco_id}",tags=["Validation"]) 
def validate_single(reco_id:int): return validate_one(reco_id)

@app.get("/accuracy",tags=["Validation"]) 
def accuracy(): return get_accuracy()

@app.get("/accuracy/log",tags=["Validation"])
def accuracy_log(reco_id:Optional[int]=None,limit:int=100): return get_validation_log(reco_id=reco_id,limit=limit)

@app.get("/journal",tags=["Journal"]) 
def journal(): return get_trades()

@app.get("/journal/open",tags=["Journal"]) 
def open_trades(): return get_trades(status="OPEN")

@app.get("/journal/analytics",tags=["Journal"]) 
def journal_analytics(): return get_analytics()

@app.post("/trade",tags=["Journal"])
def add_trade(trade:TradeIn):
    tid=insert_trade(trade.dict())
    if trade.conviction: log_prediction(trade_id=tid,stock=trade.stock,conviction=trade.conviction,predicted="BULLISH" if trade.conviction.get("total",0)>=7 else "NEUTRAL")
    return {"status":"added","trade_id":tid}

@app.put("/trade/{trade_id}/close",tags=["Journal"])
def close_trade_ep(trade_id:int,body:CloseIn):
    r=close_trade(trade_id,body.exit_price)
    if "error" in r: raise HTTPException(404,r["error"])
    close_prediction(trade_id,r["pnl"]); return r

@app.get("/intraday/positions",tags=["Intraday"]) 
def live_positions(): return get_live_positions()

@app.get("/intraday/quote/{symbol}",tags=["Intraday"])
def live_quote(symbol:str): return get_live_quote(symbol.upper())

@app.get("/intraday/ticks/{symbol}",tags=["Intraday"])
def intraday_ticks(symbol:str,limit:int=50): return get_intraday_ticks(symbol.upper(),limit)

@app.get("/intraday/alerts",tags=["Intraday"])
def intraday_alerts(limit:int=50): return get_pending_alerts(limit)

@app.post("/intraday/monitor/start",tags=["Intraday"]) 
def monitor_start(): return start_monitor()

@app.post("/intraday/monitor/stop",tags=["Intraday"]) 
def monitor_stop_ep(): return stop_monitor()

@app.get("/intraday/monitor/status",tags=["Intraday"]) 
def monitor_status(): return get_monitor_status()

@app.post("/alerts/test/telegram",tags=["Alerts"]) 
def test_tg(): return test_telegram()

@app.get("/alerts/config",tags=["Alerts"]) 
def alert_cfg(): return get_alert_config()

@app.put("/alerts/config",tags=["Alerts"])
def update_alerts(body:AlertConfigIn): return update_alert_config(body.dict(exclude_none=True))

@app.get("/alerts/log",tags=["Alerts"])
def alert_log_ep(limit:int=100): return get_alert_log(limit)

@app.post("/backtest/run",tags=["Backtesting"])
def backtest_run(body:BacktestIn,bg:BackgroundTasks):
    def _b(): run_backtest(body.symbols,body.tier,body.strategies,body.lookback_days,body.run_name)
    bg.add_task(_b); return {"status":"started"}

@app.get("/backtest/results",tags=["Backtesting"]) 
def backtest_results(): return get_backtest_results()

@app.get("/backtest/results/{run_id}",tags=["Backtesting"])
def backtest_detail(run_id:int):
    r=get_backtest_results(run_id)
    if not r: raise HTTPException(404,"Not found")
    return r

@app.get("/backtest/summary",tags=["Backtesting"]) 
def backtest_summary(): return get_backtest_summary()

@app.post("/fii/fetch",tags=["FII/DII"]) 
def fii_fetch(): return fetch_and_store()

@app.get("/fii/latest",tags=["FII/DII"]) 
def fii_latest(): return get_latest()

@app.get("/fii/history",tags=["FII/DII"])
def fii_history(days:int=30): return get_history(days)

@app.get("/fii/signals",tags=["FII/DII"]) 
def fii_signals(days:int=30): return get_signals(days)

@app.get("/fii/bias",tags=["FII/DII"]) 
def fii_bias(): return get_flow_bias()

@app.get("/learning/performance",tags=["Learning"]) 
def learning_performance(): return get_performance()
