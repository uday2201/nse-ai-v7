"""
data_fetcher.py — Parallel batch fetcher with rate-limit handling

Fetch times:
   50 stocks  →  ~1.5 min
  100 stocks  →  ~3 min
  200 stocks  →  ~6 min
  500 stocks  →  ~15 min
"""

from nsepython import equity_history
import pandas as pd
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

logger       = logging.getLogger(__name__)
MAX_WORKERS  = 3       # parallel threads — safe for NSE
SLEEP_WORKER = 0.4     # delay per worker between requests

_scan_lock = threading.Lock()
_scan_progress = {
    "status": "idle",  # idle | fetching | complete
    "done": 0,
    "total": 0,
    "fraction": 0.0,
}


def _set_scan_progress(done: int, total: int, status: str | None = None) -> None:
    with _scan_lock:
        _scan_progress["done"] = done
        _scan_progress["total"] = total
        _scan_progress["fraction"] = (done / total) if total else 0.0
        if status is not None:
            _scan_progress["status"] = status
        elif done >= total and total > 0:
            _scan_progress["status"] = "complete"
        elif total > 0:
            _scan_progress["status"] = "fetching"


def get_scan_progress() -> dict:
    """Snapshot of bulk OHLCV fetch progress (used by /scan/progress)."""
    with _scan_lock:
        return dict(_scan_progress)


def fetch_stock(symbol: str) -> pd.DataFrame | None:
    """Fetch 3-month OHLCV for one symbol. Returns None on failure."""
    try:
        raw = equity_history(symbol, "3months")
        df  = pd.DataFrame(raw)
        df.rename(columns={
            "CH_TIMESTAMP":        "date",
            "CH_CLOSING_PRICE":    "close",
            "CH_TRADE_HIGH_PRICE": "high",
            "CH_TRADE_LOW_PRICE":  "low",
            "CH_TOT_TRADED_QTY":   "volume",
            "CH_OPENING_PRICE":    "open",
        }, inplace=True)
        for col in ["close","high","low","volume","open"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
        return df if len(df) >= 20 else None
    except Exception as e:
        logger.warning(f"✗ {symbol}: {e}")
        return None


def fetch_bulk(symbols: list[str], workers: int = MAX_WORKERS, on_progress=None) -> dict[str, pd.DataFrame]:
    """Parallel fetch. on_progress(done, total) optional callback."""
    results, done, total = {}, 0, len(symbols)
    _set_scan_progress(0, total, "fetching" if total else "idle")

    def _worker(symbol):
        time.sleep(SLEEP_WORKER)
        return symbol, fetch_stock(symbol)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_worker, s): s for s in symbols}
        for f in as_completed(futures):
            symbol, df = f.result()
            done += 1
            if df is not None:
                results[symbol] = df
            logger.info(f"[{done}/{total}] {'✓' if df is not None else '✗'} {symbol}")
            if on_progress:
                on_progress(done, total)
            _set_scan_progress(done, total)
    _set_scan_progress(done, total, "complete" if total else "idle")
    return results


def fetch_bulk_safe(symbols: list[str], sleep: float = 0.9) -> dict[str, pd.DataFrame]:
    """Sequential fallback if NSE rate-limits parallel requests."""
    results = {}
    for i, s in enumerate(symbols, 1):
        df = fetch_stock(s)
        if df is not None:
            results[s] = df
        logger.info(f"[{i}/{len(symbols)}] {s}")
        time.sleep(sleep)
    return results
