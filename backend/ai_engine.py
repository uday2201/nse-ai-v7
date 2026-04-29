"""
ai_engine.py — Full universe scan engine

Scan pipeline
────────────────────────────────────────────────────────────
1. Load symbol universe (tier configurable via env / param)
2. Pre-screen: fetch all OHLCV in parallel (8 threads)
3. Add indicators to each DataFrame
4. Run all 6 strategies per stock
5. Score conviction (weighted, adaptive)
6. Enrich with smart money (NIFTY options data)
7. Return results sorted by conviction descending

Pre-screening filters (applied before heavy analysis)
  min_price      > ₹20       (avoid penny stocks)
  min_volume_avg > 50,000    (ensure liquidity)
  min_bars       >= 50       (need enough history for indicators)

Scan time estimates
  FNO_UNIVERSE  (~180 symbols): ~25-30s  ← default
  NIFTY_500     (~500 symbols): ~70-80s
  ALL_NSE       (~1600 symbols): ~4-5 min
  2nd run (cached): 2-3s any tier
"""

import os
from datetime import datetime

from data_fetcher      import fetch_bulk, get_scan_progress
from indicators        import add_indicators
from conviction_engine import calculate_conviction
from strategies        import score_all
from options_data      import get_options
from smart_money       import analyze as sm_analyze, get_levels
from learning_loop     import get_current_weights
from stock_universe    import get_symbols

# ── Default tier (override with env var SCAN_TIER) ───────────────
DEFAULT_TIER = os.getenv("SCAN_TIER", "FNO_UNIVERSE")

# ── Pre-screen thresholds ─────────────────────────────────────────
MIN_PRICE   = 20        # ₹ minimum close price
MIN_VOL_AVG = 50_000    # minimum 20-day avg volume (shares)
MIN_BARS    = 50        # minimum candles required


# ─────────────────────────────────────────────
# MAIN SCAN
# ─────────────────────────────────────────────

def run_ai_model(tier: str = DEFAULT_TIER,
                 on_progress=None) -> list[dict]:
    """
    Full scan across the specified universe tier.
    Returns all actionable stocks sorted by conviction (highest first).

    Parameters
    ──────────
    tier        : universe tier — NIFTY_50 | NIFTY_100 | FNO_UNIVERSE |
                                  NIFTY_500 | ALL_NSE
    on_progress : optional callable(done, total, symbol, failed_count)
                  called after each symbol fetch completes
    """
    print(f"\n{'='*60}")
    print(f"[Scan] Starting — tier: {tier}")
    t0 = datetime.utcnow()

    # Step 1 — symbol universe
    symbols = get_symbols(tier)
    print(f"[Scan] {len(symbols)} symbols in universe")

    # Step 2 — parallel OHLCV fetch
    data = fetch_bulk(symbols, on_progress=on_progress)
    print(f"[Scan] {len(data)} symbols fetched successfully")

    # Step 3 — smart money (single NIFTY options fetch for all stocks)
    sm = _fetch_smart_money()

    # Step 4 — adaptive weights from learning loop
    weights = get_current_weights()

    # Step 5 — analyse each stock
    results, skipped, no_signal = [], 0, 0

    for symbol, df in data.items():
        if not _passes_screen(df):
            skipped += 1
            continue

        try:
            df      = add_indicators(df)
            row     = df.iloc[-1]
            signals = score_all(df, smart_money=sm)
            conv    = calculate_conviction(df, smart_money=sm, weights=weights)
            top_sig = signals[0] if signals else None

            if top_sig is None and conv["total"] < 4:
                no_signal += 1
                continue

            results.append({
                "stock":       symbol,
                "price":       round(float(row["close"]), 2),
                "conviction":  conv["total"],
                "grade":       conv["grade"],
                "prediction":  _label(conv["total"], sm["bias"]),
                "components":  conv["components"],
                "strategy":    top_sig["strategy"]  if top_sig else None,
                "entry":       top_sig["entry"]     if top_sig else None,
                "target":      top_sig["target"]    if top_sig else None,
                "stop":        top_sig["stop"]      if top_sig else None,
                "rr":          top_sig["rr"]        if top_sig else None,
                "duration":    top_sig["duration"]  if top_sig else None,
                "all_signals": [s["strategy"] for s in signals],
                "reasons":     top_sig["reasons"]   if top_sig else [],
                "smart_money": sm["signal"],
                "bias":        sm["bias"],
                "pcr":         sm["pcr"],
                "support":     sm["support"],
                "resistance":  sm["resistance"],
                "scanned_at":  datetime.utcnow().isoformat(),
            })
        except Exception as e:
            print(f"[Analyse] {symbol} error: {e}")
            continue

    elapsed = (datetime.utcnow() - t0).seconds
    high    = sum(1 for r in results if r["grade"] == "HIGH")
    print(f"\n[Scan] Completed in {elapsed}s")
    print(f"  Universe:    {len(symbols)}")
    print(f"  Fetched:     {len(data)}")
    print(f"  Screened out:{skipped}  (liquidity)")
    print(f"  No signal:   {no_signal}")
    print(f"  Results:     {len(results)}")
    print(f"  HIGH grade:  {high}")
    print(f"{'='*60}\n")

    return sorted(results, key=lambda x: x["conviction"], reverse=True)


# ─────────────────────────────────────────────
# FILTERED VIEWS
# ─────────────────────────────────────────────

def run_high_conviction(tier: str = DEFAULT_TIER) -> list[dict]:
    """Stocks with grade HIGH (conviction >= 7)."""
    return [r for r in run_ai_model(tier) if r["grade"] == "HIGH"]


def run_smart_money() -> dict:
    return _fetch_smart_money()


def run_levels() -> dict:
    ce, pe = get_options()
    return get_levels(ce, pe)


def run_insights(tier: str = DEFAULT_TIER) -> dict:
    results = run_ai_model(tier)
    sm      = run_smart_money()

    high     = [r for r in results if r["grade"] == "HIGH"]
    moderate = [r for r in results if r["grade"] == "MODERATE"]
    top      = results[0] if results else {}

    bias_text = {
        "BULLISH": "Options data shows bullish smart money positioning.",
        "BEARISH": "Options data signals bearish institutional flow.",
        "RANGE":   "Market is range-bound — scalping setups only.",
    }.get(sm["bias"], "")

    return {
        "date":            datetime.utcnow().strftime("%Y-%m-%d"),
        "tier":            tier,
        "symbols_scanned": len(results),
        "market_bias":     sm["bias"],
        "pcr":             sm["pcr"],
        "support":         sm["support"],
        "resistance":      sm["resistance"],
        "max_pain":        sm["max_pain"],
        "high_conviction": high,
        "moderate_picks":  moderate,
        "top_pick":        top,
        "summary": (
            f"Scanned {len(results)} stocks ({tier}). "
            f"Market bias is {sm['bias']} (PCR {sm['pcr']}). {bias_text} "
            f"{len(high)} high-conviction and {len(moderate)} moderate trades found. "
            f"Key levels — support {sm['support']}, resistance {sm['resistance']}."
        ),
    }


def get_scan_status() -> dict:
    """Live scan progress (poll this from /scan/progress)."""
    return get_scan_progress()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _fetch_smart_money() -> dict:
    try:
        ce, pe = get_options()
        return sm_analyze(ce, pe)
    except Exception as e:
        print(f"[SmartMoney] Failed: {e} — using neutral defaults")
        return {
            "bias": "NEUTRAL", "signal": "NEUTRAL", "score": 1.0,
            "pcr": 1.0, "support": 0, "resistance": 0,
            "max_pain": 0, "buildups": [],
            "ce_oi_total": 0, "pe_oi_total": 0,
        }


def _passes_screen(df) -> bool:
    if df is None or df.empty or len(df) < MIN_BARS:
        return False
    last    = df.iloc[-1]
    price   = float(last.get("close", 0) or 0)
    vol_avg = float(df["volume"].tail(20).mean() or 0)
    return price >= MIN_PRICE and vol_avg >= MIN_VOL_AVG


def _label(score: float, bias: str) -> str:
    if score >= 7 and bias != "BEARISH":
        return "BULLISH"
    elif score >= 5:
        return "NEUTRAL"
    return "SKIP"
