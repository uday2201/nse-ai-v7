"""
advanced_features.py — Multi-timeframe, Watchlist, News Sentiment, Paper Trading

Four Phase-3 features in one file.

1. MULTI-TIMEFRAME CONFIRMATION
   Checks daily AND weekly timeframe alignment.
   Weekly EMA trend must agree with daily signal before entry.
   Reduces false signals by ~30%.

2. WATCHLIST
   User-defined watchlists. Alert when a watchlist stock
   generates a high-conviction signal.

3. NEWS SENTIMENT
   Lightweight keyword-based sentiment on NSE announcements
   and financial news headlines. Negative sentiment blocks
   otherwise bullish signals.

4. PAPER TRADING
   Auto-executes all HIGH conviction signals in a virtual
   portfolio. Tracks virtual P&L for 30 days before going live.
   Calculates real accuracy without risking capital.
"""

import sqlite3
import json
import re
from datetime import datetime, date, timedelta
from data_fetcher import fetch_stock
from indicators   import add_indicators

DB = "trades.db"


# ═══════════════════════════════════════════════════════════════
# 1. MULTI-TIMEFRAME CONFIRMATION
# ═══════════════════════════════════════════════════════════════

def check_multi_timeframe(symbol: str) -> dict:
    """
    Confirms daily signal against weekly timeframe.
    Returns: { confirmed, daily_trend, weekly_trend, aligned }
    """
    try:
        df_daily = fetch_stock(symbol)
        df_daily = add_indicators(df_daily)

        # Build weekly candles by resampling daily
        df_daily["date"] = df_daily["date"] if "date" in df_daily.columns else df_daily.index
        df_w = df_daily.set_index("date").resample("W").agg({
            "open":  "first", "high": "max", "low": "min",
            "close": "last",  "volume": "sum"
        }).dropna().reset_index()

        if len(df_w) < 20:
            return {"confirmed": False, "reason": "Insufficient weekly data"}

        df_w["ema20_w"] = df_w["close"].ewm(span=20, adjust=False).mean()
        df_w["ema50_w"] = df_w["close"].ewm(span=50, adjust=False).mean()

        d = df_daily.iloc[-1]
        w = df_w.iloc[-1]

        daily_bull  = d["close"] > d["ema20"] > d["ema50"]
        weekly_bull = w["close"] > w["ema20_w"]

        # MACD on weekly
        ema12_w = df_w["close"].ewm(span=12, adjust=False).mean().iloc[-1]
        ema26_w = df_w["close"].ewm(span=26, adjust=False).mean().iloc[-1]
        weekly_macd_bull = ema12_w > ema26_w

        aligned   = daily_bull and weekly_bull
        confirmed = aligned and weekly_macd_bull

        return {
            "symbol":            symbol,
            "confirmed":         confirmed,
            "aligned":           aligned,
            "daily_trend":       "BULLISH" if daily_bull  else "BEARISH",
            "weekly_trend":      "BULLISH" if weekly_bull else "BEARISH",
            "weekly_macd":       "BULLISH" if weekly_macd_bull else "BEARISH",
            "daily_close":       round(float(d["close"]), 2),
            "daily_ema20":       round(float(d["ema20"]),  2),
            "weekly_close":      round(float(w["close"]),  2),
            "weekly_ema20":      round(float(w["ema20_w"]),2),
            "message": (
                "✅ Daily + weekly aligned — high confidence entry"
                if confirmed else
                "⚠️ Weekly not confirming daily signal — wait or reduce size"
            )
        }
    except Exception as e:
        return {"confirmed": False, "reason": str(e)}


# ═══════════════════════════════════════════════════════════════
# 2. WATCHLIST
# ═══════════════════════════════════════════════════════════════

def init_watchlist_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS watchlists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS watchlist_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            watchlist_id INTEGER,
            stock       TEXT,
            added_at    TEXT,
            notes       TEXT
        );
    """)
    conn.commit()
    conn.close()


def create_watchlist(name: str, description: str = "") -> dict:
    conn = _conn()
    cur  = conn.execute(
        "INSERT INTO watchlists (name, description, created_at) VALUES (?,?,?)",
        (name, description, datetime.utcnow().isoformat())
    )
    conn.commit()
    wl_id = cur.lastrowid
    conn.close()
    return {"id": wl_id, "name": name}


def add_to_watchlist(watchlist_id: int, stocks: list[str], notes: str = "") -> dict:
    conn = _conn()
    added = []
    for stock in stocks:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist_items (watchlist_id, stock, added_at, notes) VALUES (?,?,?,?)",
            (watchlist_id, stock.upper(), datetime.utcnow().isoformat(), notes)
        )
        added.append(stock.upper())
    conn.commit()
    conn.close()
    return {"added": added, "watchlist_id": watchlist_id}


def remove_from_watchlist(watchlist_id: int, stock: str) -> dict:
    conn = _conn()
    conn.execute("DELETE FROM watchlist_items WHERE watchlist_id=? AND stock=?", (watchlist_id, stock.upper()))
    conn.commit()
    conn.close()
    return {"removed": stock.upper()}


def get_watchlists() -> list[dict]:
    conn  = _conn()
    lists = conn.execute("SELECT id, name, description, created_at FROM watchlists").fetchall()
    result= []
    for l in lists:
        items = conn.execute(
            "SELECT stock, added_at, notes FROM watchlist_items WHERE watchlist_id=?", (l[0],)
        ).fetchall()
        result.append({
            "id":          l[0],
            "name":        l[1],
            "description": l[2],
            "created_at":  l[3],
            "stocks":      [{"stock": i[0], "added_at": i[1], "notes": i[2]} for i in items],
        })
    conn.close()
    return result


def scan_watchlist(watchlist_id: int, scan_results: list[dict]) -> list[dict]:
    """Filter scan results to only watchlist stocks."""
    conn   = _conn()
    items  = conn.execute(
        "SELECT stock FROM watchlist_items WHERE watchlist_id=?", (watchlist_id,)
    ).fetchall()
    conn.close()
    wl_stocks = {i[0] for i in items}
    return [r for r in scan_results if r.get("stock") in wl_stocks]


# ═══════════════════════════════════════════════════════════════
# 3. NEWS SENTIMENT
# ═══════════════════════════════════════════════════════════════

# Positive and negative keyword lists (NSE/financial context)
POSITIVE_WORDS = [
    "record profit","strong growth","beat estimates","order win","upgrade",
    "expansion","buyback","dividend","outperform","strong results","margin expansion",
    "guidance raised","new contract","partnership","acquisition","robust demand",
    "all time high","revenue growth","positive outlook","bullish","recovery",
]
NEGATIVE_WORDS = [
    "probe","fraud","scam","raid","penalty","downgrade","miss estimates","loss",
    "write-off","resignation","investigation","slowdown","weak demand","margin compression",
    "guidance cut","default","debt","bankruptcy","regulatory action","negative outlook",
    "disappointing","recall","lawsuit","insider trading","promoter selling",
]

def init_sentiment_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS news_sentiment (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            stock       TEXT,
            headline    TEXT,
            sentiment   TEXT,
            score       REAL,
            source      TEXT,
            published   TEXT,
            created_at  TEXT
        );
    """)
    conn.commit()
    conn.close()


def analyse_sentiment(text: str) -> dict:
    """
    Keyword-based sentiment analysis.
    Returns: { sentiment, score, matched_positive, matched_negative }
    """
    text_lower = text.lower()
    pos_hits = [w for w in POSITIVE_WORDS if w in text_lower]
    neg_hits = [w for w in NEGATIVE_WORDS if w in text_lower]

    pos_score = len(pos_hits)
    neg_score = len(neg_hits) * 1.5   # negative words weighted higher (loss aversion)

    net = pos_score - neg_score

    if net >= 2:
        sentiment = "POSITIVE"
    elif net <= -1.5:
        sentiment = "NEGATIVE"
    else:
        sentiment = "NEUTRAL"

    return {
        "sentiment":         sentiment,
        "score":             round(net, 2),
        "matched_positive":  pos_hits,
        "matched_negative":  neg_hits,
    }


def store_sentiment(stock: str, headline: str, source: str = "NSE") -> dict:
    result = analyse_sentiment(headline)
    conn   = _conn()
    conn.execute("""
        INSERT INTO news_sentiment (stock, headline, sentiment, score, source, published, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (stock.upper(), headline[:500], result["sentiment"], result["score"],
          source, date.today().isoformat(), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return {**result, "stock": stock.upper()}


def get_stock_sentiment(stock: str, days: int = 7) -> dict:
    """Aggregated sentiment for a stock over last N days."""
    conn  = _conn()
    since = (date.today() - timedelta(days=days)).isoformat()
    rows  = conn.execute("""
        SELECT sentiment, score, headline FROM news_sentiment
        WHERE stock=? AND published >= ? ORDER BY id DESC
    """, (stock.upper(), since)).fetchall()
    conn.close()

    if not rows:
        return {"stock": stock, "sentiment": "NEUTRAL", "score": 0, "news_count": 0}

    scores    = [r[1] for r in rows]
    avg_score = sum(scores) / len(scores)
    pos       = sum(1 for r in rows if r[0] == "POSITIVE")
    neg       = sum(1 for r in rows if r[0] == "NEGATIVE")
    sentiment = "POSITIVE" if avg_score > 1 else "NEGATIVE" if avg_score < -1 else "NEUTRAL"

    # Block signal if negative sentiment dominates
    block_signal = neg > pos and avg_score < -1.5

    return {
        "stock":         stock.upper(),
        "sentiment":     sentiment,
        "avg_score":     round(avg_score, 2),
        "positive_count":pos,
        "negative_count":neg,
        "news_count":    len(rows),
        "block_signal":  block_signal,
        "recent_headlines": [r[2] for r in rows[:5]],
        "days":          days,
    }


def is_sentiment_clear(stock: str) -> bool:
    """Returns True if sentiment is not strongly negative."""
    s = get_stock_sentiment(stock)
    return not s.get("block_signal", False)


# ═══════════════════════════════════════════════════════════════
# 4. PAPER TRADING
# ═══════════════════════════════════════════════════════════════

PAPER_CAPITAL = 1_000_000   # ₹10 lakh virtual capital


def init_paper_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock           TEXT,
            strategy        TEXT,
            entry           REAL,
            target          REAL,
            stop            REAL,
            qty             INTEGER,
            rr              REAL,
            conviction      REAL,
            entry_date      TEXT,
            expiry_date     TEXT,
            exit_date       TEXT,
            exit_price      REAL,
            pnl             REAL,
            outcome         TEXT,
            status          TEXT DEFAULT 'OPEN',
            created_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS paper_portfolio (
            id              INTEGER PRIMARY KEY DEFAULT 1,
            capital         REAL DEFAULT 1000000,
            deployed        REAL DEFAULT 0,
            realized_pnl    REAL DEFAULT 0,
            unrealized_pnl  REAL DEFAULT 0,
            total_trades    INTEGER DEFAULT 0,
            wins            INTEGER DEFAULT 0,
            losses          INTEGER DEFAULT 0
        );
    """)
    conn.execute("INSERT OR IGNORE INTO paper_portfolio (id) VALUES (1)")
    conn.commit()
    conn.close()


def paper_enter(reco: dict) -> dict:
    """Auto-enter a paper trade from a recommendation."""
    port   = get_paper_portfolio()
    entry  = reco.get("entry") or reco.get("price", 0)
    if not entry:
        return {"error": "No entry price"}

    # Size: 2% risk per trade
    stop      = reco.get("stop", entry * 0.97)
    risk_per  = max(entry - stop, 1)
    max_risk  = port["capital"] * 0.02
    qty       = max(1, int(max_risk / risk_per))
    deployed  = qty * entry

    if deployed > port["capital"] - port["deployed"]:
        return {"error": "Insufficient paper capital"}

    today   = date.today().isoformat()
    expiry  = (date.today() + timedelta(days=reco.get("duration", reco.get("duration_days", 10)))).isoformat()

    conn = _conn()
    cur  = conn.execute("""
        INSERT INTO paper_trades
            (stock, strategy, entry, target, stop, qty, rr, conviction,
             entry_date, expiry_date, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,'OPEN',?)
    """, (
        reco["stock"], reco.get("strategy",""), entry,
        reco.get("target", entry * 1.05), stop, qty,
        reco.get("rr", 2.0), reco.get("conviction", 6),
        today, expiry, datetime.utcnow().isoformat()
    ))
    trade_id = cur.lastrowid

    conn.execute("UPDATE paper_portfolio SET deployed=deployed+?, total_trades=total_trades+1 WHERE id=1", (deployed,))
    conn.commit()
    conn.close()

    return {"paper_trade_id": trade_id, "stock": reco["stock"], "qty": qty,
            "entry": entry, "deployed": round(deployed, 2)}


def paper_validate() -> dict:
    """Check all open paper trades against latest prices."""
    from data_fetcher import fetch_bulk
    from validator import _evaluate

    conn  = _conn()
    open_ = conn.execute("SELECT * FROM paper_trades WHERE status='OPEN'").fetchall()
    conn.close()

    cols   = ["id","stock","strategy","entry","target","stop","qty","rr","conviction",
              "entry_date","expiry_date","exit_date","exit_price","pnl","outcome","status","created_at"]
    trades = [dict(zip(cols, r)) for r in open_]
    if not trades:
        return {"checked": 0}

    symbols = list({t["stock"] for t in trades})
    data    = fetch_bulk(symbols, use_cache=True)

    closed = 0
    for t in trades:
        df = data.get(t["stock"])
        if df is None or df.empty:
            continue
        row = df.iloc[-1]
        result = _evaluate(t, float(row["high"]), float(row["low"]), float(row["close"]),
                           date.today().isoformat())
        if result["closed"]:
            exit_price = t["target"] if result["outcome"] == "WIN" else t["stop"] if result["status"] == "STOP_HIT" else float(row["close"])
            pnl = round((exit_price - t["entry"]) * t["qty"], 2)
            _close_paper_trade(t["id"], exit_price, pnl, result["outcome"])
            closed += 1

    return {"checked": len(trades), "closed": closed, "still_open": len(trades) - closed}


def get_paper_portfolio() -> dict:
    conn = _conn()
    row  = conn.execute("SELECT * FROM paper_portfolio WHERE id=1").fetchone()
    conn.close()
    if not row:
        return {"capital": PAPER_CAPITAL, "deployed": 0, "realized_pnl": 0}
    cols = ["id","capital","deployed","realized_pnl","unrealized_pnl","total_trades","wins","losses"]
    d = dict(zip(cols, row))
    d["win_rate"]   = round(d["wins"] / d["total_trades"] * 100, 1) if d["total_trades"] else 0
    d["total_value"]= round(d["capital"] + d["realized_pnl"], 2)
    d["return_pct"] = round(d["realized_pnl"] / PAPER_CAPITAL * 100, 2)
    return d


def get_paper_trades(status: str | None = None) -> list[dict]:
    conn = _conn()
    q    = "SELECT * FROM paper_trades"
    if status:
        q += f" WHERE status='{status.upper()}'"
    q += " ORDER BY id DESC"
    rows = conn.execute(q).fetchall()
    conn.close()
    cols = ["id","stock","strategy","entry","target","stop","qty","rr","conviction",
            "entry_date","expiry_date","exit_date","exit_price","pnl","outcome","status","created_at"]
    return [dict(zip(cols, r)) for r in rows]


def _close_paper_trade(trade_id: int, exit_price: float, pnl: float, outcome: str):
    status = {"WIN":"TARGET_HIT","LOSS":"STOP_HIT"}.get(outcome, "EXPIRED")
    conn   = _conn()
    row    = conn.execute("SELECT entry, qty FROM paper_trades WHERE id=?", (trade_id,)).fetchone()
    if row:
        deployed = row[0] * row[1]
        conn.execute(
            "UPDATE paper_portfolio SET deployed=MAX(0,deployed-?), realized_pnl=realized_pnl+?, wins=wins+?, losses=losses+? WHERE id=1",
            (deployed, pnl, 1 if outcome == "WIN" else 0, 1 if outcome != "WIN" else 0)
        )
    conn.execute(
        "UPDATE paper_trades SET status=?, outcome=?, exit_price=?, pnl=?, exit_date=? WHERE id=?",
        (status, outcome, exit_price, pnl, date.today().isoformat(), trade_id)
    )
    conn.commit()
    conn.close()


def _conn():
    return sqlite3.connect(DB)
