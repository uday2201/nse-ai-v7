"""
recommendation_engine.py — Full universe recommendation generator

Scans the configured universe, runs all 6 strategies per stock,
saves recommendations with entry/target/stop/duration to SQLite.
"""

import json, sqlite3
from datetime import datetime, timedelta

from data_fetcher      import fetch_bulk
from indicators        import add_indicators
from strategies        import score_all
from smart_money       import analyze as sm_analyze
from options_data      import get_options
from conviction_engine import calculate_conviction
from learning_loop     import get_current_weights
from stock_universe    import get_symbols

DB             = "trades.db"
SCAN_UNIVERSE  = "nifty100"   # change to nifty500 for full scan
MIN_CONFIDENCE = 5.0


def init_reco_table():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock           TEXT    NOT NULL,
            strategy        TEXT    NOT NULL,
            direction       TEXT    DEFAULT 'LONG',
            entry           REAL    NOT NULL,
            target          REAL    NOT NULL,
            stop            REAL    NOT NULL,
            rr              REAL,
            duration_days   INTEGER NOT NULL,
            expiry_date     TEXT    NOT NULL,
            conviction      REAL,
            reasons         TEXT,
            status          TEXT    DEFAULT 'OPEN',
            outcome         TEXT,
            exit_price      REAL,
            exit_date       TEXT,
            max_price       REAL,
            min_price       REAL,
            created_at      TEXT,
            last_checked    TEXT
        );
        CREATE TABLE IF NOT EXISTS validation_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            reco_id    INTEGER,
            stock      TEXT,
            check_date TEXT,
            price      REAL,
            high       REAL,
            low        REAL,
            status     TEXT,
            note       TEXT
        );
    """)
    conn.commit()
    conn.close()


def generate_recommendations(universe: str = SCAN_UNIVERSE) -> list[dict]:
    """
    Full scan of `universe`. Runs all strategies per stock.
    Returns list of new recommendations saved to DB.
    """
    symbols = get_symbols(universe)
    data    = fetch_bulk(symbols)
    ce, pe  = get_options()
    sm      = sm_analyze(ce, pe)
    weights = get_current_weights()

    new_recos = []
    for symbol, df in data.items():
        if df.empty or len(df) < 50:
            continue
        df      = add_indicators(df)
        signals = score_all(df, smart_money=sm)
        if not signals or signals[0]["confidence"] < MIN_CONFIDENCE:
            continue

        sig        = signals[0]
        conviction = calculate_conviction(df, smart_money=sm, weights=weights)

        if _already_open(symbol, sig["strategy"]):
            continue

        reco = _save_reco(symbol, sig, conviction["total"])
        new_recos.append(reco)

    return sorted(new_recos, key=lambda x: x["conviction"], reverse=True)


def get_recommendations(status: str | None = None) -> list[dict]:
    conn = _conn()
    q    = "SELECT * FROM recommendations"
    if status:
        q += f" WHERE status = '{status.upper()}'"
    rows = conn.execute(q + " ORDER BY id DESC").fetchall()
    conn.close()
    return [_row(r) for r in rows]


def get_reco_by_id(reco_id: int) -> dict | None:
    conn = _conn()
    row  = conn.execute("SELECT * FROM recommendations WHERE id=?", (reco_id,)).fetchone()
    conn.close()
    return _row(row) if row else None


def _save_reco(symbol, sig, conviction):
    now    = datetime.utcnow()
    expiry = (now + timedelta(days=sig["duration"])).strftime("%Y-%m-%d")
    conn   = _conn()
    cur    = conn.execute("""
        INSERT INTO recommendations
          (stock,strategy,direction,entry,target,stop,rr,
           duration_days,expiry_date,conviction,reasons,
           status,outcome,created_at,last_checked)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,'OPEN','OPEN',?,?)
    """, (symbol, sig["strategy"], sig["direction"], sig["entry"], sig["target"],
          sig["stop"], sig["rr"], sig["duration"], expiry, conviction,
          json.dumps(sig["reasons"]), now.isoformat(), now.isoformat()))
    conn.commit()
    reco_id = cur.lastrowid
    conn.close()
    return {"id":reco_id,"stock":symbol,"strategy":sig["strategy"],
            "direction":sig["direction"],"entry":sig["entry"],
            "target":sig["target"],"stop":sig["stop"],"rr":sig["rr"],
            "duration":sig["duration"],"expiry":expiry,
            "conviction":conviction,"reasons":sig["reasons"]}


def _already_open(symbol, strategy):
    conn = _conn()
    row  = conn.execute("SELECT id FROM recommendations WHERE stock=? AND strategy=? AND status='OPEN'", (symbol, strategy)).fetchone()
    conn.close()
    return row is not None

def _conn():    return sqlite3.connect(DB)
def _cols():    return ["id","stock","strategy","direction","entry","target","stop","rr","duration_days","expiry_date","conviction","reasons","status","outcome","exit_price","exit_date","max_price","min_price","created_at","last_checked"]
def _row(r):
    d = dict(zip(_cols(), r))
    try:    d["reasons"] = json.loads(d["reasons"] or "[]")
    except: d["reasons"] = []
    return d
