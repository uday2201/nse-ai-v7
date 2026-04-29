"""
options_strategy.py — Options strategy builder

Based on conviction score, market bias, PCR and IV level,
suggests the optimal options structure for each trade.

Strategies suggested
────────────────────────────────────────────────────────────
BULL_CALL_SPREAD   High conviction + low IV + bullish bias
                   Buy ATM call, sell OTM call
                   Max loss = premium, capped profit

BULL_PUT_SPREAD    High conviction + medium IV + bullish
                   Sell OTM put, buy further OTM put
                   Credit strategy — profit if stock stays up

COVERED_CALL       Stock position + sell OTM call
                   Enhances return on MODERATE conviction longs

IRON_CONDOR        Low conviction + high IV + range bias
                   Sell strangle, buy further strangle
                   Profit if stock stays within range

LONG_CALL          Highest conviction + low IV + trend breakout
                   Pure directional — for ADX_BREAKOUT signals

CASH_SECURED_PUT   Moderate conviction — want to buy stock cheaper
                   Sell ATM put, collect premium
                   Enter stock at lower effective cost

Each strategy output includes:
  strikes, premiums (estimated), max_loss, max_profit,
  breakeven, probability_of_profit (simplified)
"""

import sqlite3
from datetime import datetime, date
from nsepython import nse_optionchain_scrapper
import pandas as pd

DB = "trades.db"


# ─────────────────────────────────────────────
# DB SCHEMA
# ─────────────────────────────────────────────

def init_options_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS options_strategies (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock           TEXT,
            strategy_type   TEXT,
            direction       TEXT,
            spot_price      REAL,
            expiry          TEXT,
            legs            TEXT,   -- JSON
            max_loss        REAL,
            max_profit      REAL,
            breakeven       REAL,
            pop             REAL,   -- probability of profit
            iv_rank         REAL,
            conviction      REAL,
            rationale       TEXT,
            created_at      TEXT
        );
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# MAIN: SUGGEST STRATEGY
# ─────────────────────────────────────────────

def suggest_options_strategy(
    stock:      str,
    spot_price: float,
    conviction: float,
    bias:       str,         # BULLISH | BEARISH | RANGE
    pcr:        float,
    strategy_signal: str,    # from strategies.py
) -> dict:
    """
    Suggest best options structure for a stock given conviction and market context.
    """
    # Fetch live option chain for the stock (or NIFTY for index trades)
    chain = _fetch_chain(stock)
    iv_rank = _estimate_iv_rank(chain, spot_price)

    # Pick strategy
    strategy_type, legs, rationale = _pick_strategy(
        conviction, bias, pcr, iv_rank, spot_price, chain, strategy_signal
    )

    if not legs:
        return {"error": "No suitable options strategy for current conditions"}

    metrics = _compute_metrics(legs, spot_price, strategy_type)

    result = {
        "stock":          stock,
        "strategy_type":  strategy_type,
        "spot_price":     round(spot_price, 2),
        "iv_rank":        round(iv_rank, 1),
        "conviction":     conviction,
        "bias":           bias,
        "legs":           legs,
        "max_loss":       metrics["max_loss"],
        "max_profit":     metrics["max_profit"],
        "breakeven":      metrics["breakeven"],
        "pop":            metrics["pop"],
        "rationale":      rationale,
        "created_at":     datetime.utcnow().isoformat(),
    }

    _save_strategy(result)
    return result


# ─────────────────────────────────────────────
# STRATEGY SELECTION LOGIC
# ─────────────────────────────────────────────

def _pick_strategy(conviction, bias, pcr, iv_rank, spot, chain, signal):
    """
    Decision matrix:
    IV_RANK  <30 = low IV   (buy options — cheap)
    IV_RANK  >60 = high IV  (sell options — expensive)
    """
    # ── Strong bullish, low IV → Long Call or Bull Call Spread ─────
    if conviction >= 7.5 and bias == "BULLISH" and iv_rank < 35:
        if conviction >= 8.5 and signal in ("ADX_BREAKOUT","EMA_TREND_FOLLOW"):
            return _long_call(spot, chain)
        return _bull_call_spread(spot, chain)

    # ── Strong bullish, high IV → Bull Put Spread (credit) ────────
    if conviction >= 7 and bias == "BULLISH" and iv_rank >= 40:
        return _bull_put_spread(spot, chain)

    # ── Moderate bullish + stock holding → Covered Call ───────────
    if 5 <= conviction < 7.5 and bias == "BULLISH":
        return _covered_call(spot, chain)

    # ── Range market + high IV → Iron Condor ──────────────────────
    if bias == "RANGE" and iv_rank >= 50 and pcr >= 0.9 and pcr <= 1.2:
        return _iron_condor(spot, chain)

    # ── Moderate conviction, want lower entry → Cash Secured Put ──
    if 5 <= conviction < 7 and bias in ("BULLISH","RANGE") and iv_rank >= 35:
        return _cash_secured_put(spot, chain)

    return None, [], "No strategy — conviction too low or conditions unclear"


# ─────────────────────────────────────────────
# STRATEGY BUILDERS
# ─────────────────────────────────────────────

def _long_call(spot: float, chain: pd.DataFrame):
    strike = _atm(spot, chain, "CE")
    prem   = _get_premium(chain, strike, "CE")
    rationale = (
        f"LONG CALL at ₹{strike}: High conviction trend breakout signal. "
        f"IV is low (options cheap). Max loss = premium ₹{prem}. "
        f"Pure directional — profit if stock rallies strongly."
    )
    legs = [{"action":"BUY","type":"CE","strike":strike,"premium":prem,"qty":1}]
    return "LONG_CALL", legs, rationale


def _bull_call_spread(spot: float, chain: pd.DataFrame):
    buy_strike  = _atm(spot, chain, "CE")
    sell_strike = _otm(spot, chain, "CE", pct=0.03)
    buy_prem    = _get_premium(chain, buy_strike, "CE")
    sell_prem   = _get_premium(chain, sell_strike, "CE")
    net_debit   = round(buy_prem - sell_prem, 2)
    rationale = (
        f"BULL CALL SPREAD {buy_strike}/{sell_strike}: "
        f"Net debit ₹{net_debit}. Capped profit but lower cost vs naked call. "
        f"Best if stock moves up 3-5%."
    )
    legs = [
        {"action":"BUY",  "type":"CE","strike":buy_strike,  "premium":buy_prem,  "qty":1},
        {"action":"SELL", "type":"CE","strike":sell_strike, "premium":sell_prem, "qty":1},
    ]
    return "BULL_CALL_SPREAD", legs, rationale


def _bull_put_spread(spot: float, chain: pd.DataFrame):
    sell_strike = _otm(spot, chain, "PE", pct=0.02)
    buy_strike  = _otm(spot, chain, "PE", pct=0.05)
    sell_prem   = _get_premium(chain, sell_strike, "PE")
    buy_prem    = _get_premium(chain, buy_strike,  "PE")
    credit      = round(sell_prem - buy_prem, 2)
    rationale = (
        f"BULL PUT SPREAD {sell_strike}/{buy_strike}: "
        f"Net credit ₹{credit}. Profit if stock stays above {sell_strike}. "
        f"High IV makes sold put expensive — collect premium."
    )
    legs = [
        {"action":"SELL","type":"PE","strike":sell_strike,"premium":sell_prem,"qty":1},
        {"action":"BUY", "type":"PE","strike":buy_strike, "premium":buy_prem, "qty":1},
    ]
    return "BULL_PUT_SPREAD", legs, rationale


def _covered_call(spot: float, chain: pd.DataFrame):
    strike = _otm(spot, chain, "CE", pct=0.025)
    prem   = _get_premium(chain, strike, "CE")
    rationale = (
        f"COVERED CALL at ₹{strike}: Sell call against existing stock position. "
        f"Collect ₹{prem} premium. Enhances return if stock stays flat or rises moderately."
    )
    legs = [
        {"action":"HOLD","type":"STOCK","strike":round(spot,2),"premium":0,"qty":1},
        {"action":"SELL","type":"CE",   "strike":strike,       "premium":prem,"qty":1},
    ]
    return "COVERED_CALL", legs, rationale


def _iron_condor(spot: float, chain: pd.DataFrame):
    sell_ce = _otm(spot, chain, "CE", pct=0.025)
    buy_ce  = _otm(spot, chain, "CE", pct=0.045)
    sell_pe = _otm(spot, chain, "PE", pct=0.025)
    buy_pe  = _otm(spot, chain, "PE", pct=0.045)
    credit  = round(
        _get_premium(chain,sell_ce,"CE") - _get_premium(chain,buy_ce,"CE") +
        _get_premium(chain,sell_pe,"PE") - _get_premium(chain,buy_pe,"PE"), 2
    )
    rationale = (
        f"IRON CONDOR {sell_pe}/{sell_ce}: "
        f"Range-bound strategy. Net credit ₹{credit}. "
        f"Profit if stock stays between {sell_pe} and {sell_ce}. "
        f"High IV makes both sold options expensive."
    )
    legs = [
        {"action":"SELL","type":"CE","strike":sell_ce,"premium":_get_premium(chain,sell_ce,"CE"),"qty":1},
        {"action":"BUY", "type":"CE","strike":buy_ce, "premium":_get_premium(chain,buy_ce,"CE"), "qty":1},
        {"action":"SELL","type":"PE","strike":sell_pe,"premium":_get_premium(chain,sell_pe,"PE"),"qty":1},
        {"action":"BUY", "type":"PE","strike":buy_pe, "premium":_get_premium(chain,buy_pe,"PE"), "qty":1},
    ]
    return "IRON_CONDOR", legs, rationale


def _cash_secured_put(spot: float, chain: pd.DataFrame):
    strike = _otm(spot, chain, "PE", pct=0.02)
    prem   = _get_premium(chain, strike, "PE")
    eff    = round(strike - prem, 2)
    rationale = (
        f"CASH SECURED PUT at ₹{strike}: Collect ₹{prem} premium. "
        f"Effective buy price ₹{eff} if assigned (below current ₹{round(spot,2)}). "
        f"Win if stock stays flat or falls slightly."
    )
    legs = [{"action":"SELL","type":"PE","strike":strike,"premium":prem,"qty":1}]
    return "CASH_SECURED_PUT", legs, rationale


# ─────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────

def _compute_metrics(legs: list, spot: float, strategy_type: str) -> dict:
    buy_cost  = sum(l["premium"] for l in legs if l["action"] == "BUY"  and l["type"] != "STOCK")
    sell_rev  = sum(l["premium"] for l in legs if l["action"] == "SELL")
    net_cost  = round(buy_cost - sell_rev, 2)

    if strategy_type == "LONG_CALL":
        return {"max_loss": net_cost, "max_profit": None, "breakeven": round(legs[0]["strike"] + net_cost,2), "pop": 40}

    if strategy_type == "BULL_CALL_SPREAD":
        width = abs(legs[1]["strike"] - legs[0]["strike"])
        return {"max_loss": net_cost, "max_profit": round(width - net_cost,2), "breakeven": round(legs[0]["strike"] + net_cost,2), "pop": 55}

    if strategy_type == "BULL_PUT_SPREAD":
        credit = -net_cost
        width  = abs(legs[0]["strike"] - legs[1]["strike"])
        return {"max_loss": round(width - credit,2), "max_profit": credit, "breakeven": round(legs[0]["strike"] - credit,2), "pop": 65}

    if strategy_type == "IRON_CONDOR":
        credit = -net_cost
        return {"max_loss": round(abs(legs[0]["strike"]-legs[1]["strike"]) - credit,2), "max_profit": credit, "breakeven": None, "pop": 68}

    if strategy_type == "COVERED_CALL":
        prem = sell_rev
        return {"max_loss": round(spot - prem,2), "max_profit": round(legs[1]["strike"] - spot + prem,2), "breakeven": round(spot - prem,2), "pop": 70}

    if strategy_type == "CASH_SECURED_PUT":
        prem = sell_rev
        return {"max_loss": round(legs[0]["strike"] - prem,2), "max_profit": prem, "breakeven": round(legs[0]["strike"] - prem,2), "pop": 65}

    return {"max_loss": net_cost, "max_profit": None, "breakeven": None, "pop": 50}


# ─────────────────────────────────────────────
# OPTION CHAIN HELPERS
# ─────────────────────────────────────────────

def _fetch_chain(symbol: str) -> pd.DataFrame:
    try:
        data = nse_optionchain_scrapper("NIFTY" if symbol in ("NIFTY","BANKNIFTY") else symbol)
        rows = []
        for item in data.get("records",{}).get("data",[]):
            for side in ["CE","PE"]:
                if item.get(side):
                    r = item[side]
                    r["optionType"] = side
                    rows.append(r)
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def _estimate_iv_rank(chain: pd.DataFrame, spot: float) -> float:
    """Estimate IV rank — simplified. 0=low, 100=high."""
    if chain.empty or "impliedVolatility" not in chain.columns:
        return 50.0
    try:
        atm_iv = chain[
            (chain["strikePrice"].between(spot*0.98, spot*1.02)) &
            (chain["optionType"] == "CE")
        ]["impliedVolatility"].mean()
        # Rough rank: assume 52-week range 10%–80%
        return round(max(0, min(100, (atm_iv - 10) / 70 * 100)), 1)
    except Exception:
        return 50.0


def _atm(spot: float, chain: pd.DataFrame, option_type: str) -> float:
    if chain.empty:
        return round(spot / 50) * 50
    strikes = chain[chain.get("optionType","") == option_type]["strikePrice"].dropna().unique()
    if len(strikes) == 0:
        return round(spot / 50) * 50
    return float(min(strikes, key=lambda x: abs(x - spot)))


def _otm(spot: float, chain: pd.DataFrame, option_type: str, pct: float = 0.03) -> float:
    target = spot * (1 + pct) if option_type == "CE" else spot * (1 - pct)
    if chain.empty:
        return round(target / 50) * 50
    strikes = chain[chain.get("optionType","") == option_type]["strikePrice"].dropna().unique()
    if len(strikes) == 0:
        return round(target / 50) * 50
    return float(min(strikes, key=lambda x: abs(x - target)))


def _get_premium(chain: pd.DataFrame, strike: float, option_type: str) -> float:
    if chain.empty:
        return round(strike * 0.015, 2)  # rough 1.5% estimate
    try:
        row = chain[(chain["strikePrice"] == strike) & (chain.get("optionType","") == option_type)]
        if not row.empty and "lastPrice" in row.columns:
            return float(row["lastPrice"].iloc[0])
    except Exception:
        pass
    return round(strike * 0.015, 2)


def _save_strategy(r: dict):
    import json
    conn = _conn()
    conn.execute("""
        INSERT INTO options_strategies
            (stock, strategy_type, direction, spot_price, legs, max_loss, max_profit,
             breakeven, pop, iv_rank, conviction, rationale, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (r["stock"], r["strategy_type"], r["bias"], r["spot_price"],
          json.dumps(r["legs"]), r["max_loss"], r["max_profit"],
          r["breakeven"], r["pop"], r["iv_rank"], r["conviction"],
          r["rationale"], r["created_at"]))
    conn.commit()
    conn.close()


def get_saved_strategies(stock: str | None = None, limit: int = 50) -> list[dict]:
    import json
    conn = _conn()
    if stock:
        rows = conn.execute("SELECT * FROM options_strategies WHERE stock=? ORDER BY id DESC LIMIT ?", (stock, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM options_strategies ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    cols = ["id","stock","strategy_type","direction","spot_price","expiry","legs","max_loss",
            "max_profit","breakeven","pop","iv_rank","conviction","rationale","created_at"]
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        try: d["legs"] = json.loads(d["legs"] or "[]")
        except: pass
        result.append(d)
    return result


def _conn():
    return sqlite3.connect(DB)
