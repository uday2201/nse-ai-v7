"""
alerts.py — Multi-channel alert engine

Supported channels
──────────────────────────────────────────────
Telegram    — Bot API (free, instant, reliable)
WhatsApp    — Twilio API (paid, ₹1-2 per message)
Email       — SMTP (free via Gmail)

Setup (set these in .env or environment variables)
──────────────────────────────────────────────────
TELEGRAM_TOKEN      your bot token from @BotFather
TELEGRAM_CHAT_ID    your chat ID (get from @userinfobot)
TWILIO_SID          Twilio account SID (for WhatsApp)
TWILIO_AUTH         Twilio auth token
TWILIO_FROM         WhatsApp sender (whatsapp:+14155238886)
TWILIO_TO           Your WhatsApp (whatsapp:+91XXXXXXXXXX)
EMAIL_FROM          sender@gmail.com
EMAIL_PASS          Gmail app password
EMAIL_TO            recipient@gmail.com

Recommendation: use Telegram only — it's free, instant, and
supports rich formatting with charts.
"""

import os
import smtplib
import sqlite3
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from zoneinfo import ZoneInfo

try:
    import httpx
    HTTP = True
except ImportError:
    HTTP = False

DB  = "trades.db"
IST = ZoneInfo("Asia/Kolkata")

# Load config from env
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TWILIO_SID       = os.getenv("TWILIO_SID", "")
TWILIO_AUTH      = os.getenv("TWILIO_AUTH", "")
TWILIO_FROM      = os.getenv("TWILIO_FROM", "whatsapp:+14155238886")
TWILIO_TO        = os.getenv("TWILIO_TO", "")
EMAIL_FROM       = os.getenv("EMAIL_FROM", "")
EMAIL_PASS       = os.getenv("EMAIL_PASS", "")
EMAIL_TO         = os.getenv("EMAIL_TO", "")


# ─────────────────────────────────────────────
# DB SCHEMA
# ─────────────────────────────────────────────

def init_alert_tables():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel     TEXT,
            alert_type  TEXT,
            message     TEXT,
            status      TEXT,    -- SENT | FAILED
            error       TEXT,
            timestamp   TEXT
        );

        CREATE TABLE IF NOT EXISTS alert_config (
            id          INTEGER PRIMARY KEY,
            telegram    INTEGER DEFAULT 1,
            whatsapp    INTEGER DEFAULT 0,
            email       INTEGER DEFAULT 0,
            min_grade   TEXT    DEFAULT 'HIGH',   -- min conviction grade to alert
            alert_types TEXT    DEFAULT '["TARGET_HIT","STOP_HIT","NEW_SIGNAL","NEAR_TARGET","NEAR_STOP","FII_ALERT"]'
        );
    """)
    # Insert default config if not exists
    conn.execute("INSERT OR IGNORE INTO alert_config (id) VALUES (1)")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# MAIN SEND FUNCTION
# ─────────────────────────────────────────────

def send_alert(message: str, alert_type: str = "INFO", data: dict | None = None) -> dict:
    """
    Send alert to all configured channels.
    Returns dict of channel → success/fail.
    """
    config   = _get_config()
    results  = {}
    rich_msg = _format_message(message, alert_type, data)

    if config.get("telegram") and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        ok, err = _send_telegram(rich_msg)
        results["telegram"] = "SENT" if ok else f"FAILED: {err}"
        _log_alert("telegram", alert_type, message, "SENT" if ok else "FAILED", err)

    if config.get("whatsapp") and TWILIO_SID and TWILIO_TO:
        ok, err = _send_whatsapp(message)
        results["whatsapp"] = "SENT" if ok else f"FAILED: {err}"
        _log_alert("whatsapp", alert_type, message, "SENT" if ok else "FAILED", err)

    if config.get("email") and EMAIL_FROM and EMAIL_TO:
        ok, err = _send_email(alert_type, rich_msg)
        results["email"] = "SENT" if ok else f"FAILED: {err}"
        _log_alert("email", alert_type, message, "SENT" if ok else "FAILED", err)

    if not results:
        print(f"[Alert] No channels configured — message: {message}")

    return results


def send_new_signal_alert(reco: dict):
    """Alert when a new high-conviction recommendation is generated."""
    msg = (
        f"🚀 NEW SIGNAL: {reco['stock']}\n"
        f"Strategy: {reco.get('strategy','').replace('_',' ')}\n"
        f"Entry: ₹{reco.get('entry')}  Target: ₹{reco.get('target')}  Stop: ₹{reco.get('stop')}\n"
        f"R:R = {reco.get('rr')}:1  ·  Hold {reco.get('duration_days')}d\n"
        f"Conviction: {reco.get('conviction')}/10"
    )
    return send_alert(msg, "NEW_SIGNAL", reco)


def send_daily_summary(insights: dict):
    """Send morning summary with market bias and top picks."""
    high = insights.get("high_conviction", [])
    top  = insights.get("top_pick", {})
    msg = (
        f"📊 DAILY SUMMARY — {insights.get('date')}\n"
        f"Market Bias: {insights.get('market_bias')}  PCR: {insights.get('pcr')}\n"
        f"Support: {insights.get('support')}  Resistance: {insights.get('resistance')}\n"
        f"High Conviction Picks: {len(high)}\n"
    )
    if top:
        msg += f"Top Pick: {top.get('stock')} — CV {top.get('conviction')}/10"
    return send_alert(msg, "DAILY_SUMMARY", insights)


def send_fii_alert(flow: dict):
    """Alert when FII net flow crosses threshold."""
    msg = (
        f"🏦 FII/DII FLOW ALERT\n"
        f"FII Net: ₹{flow.get('fii_net_cr')} Cr  ({'BUYING 🟢' if flow.get('fii_net_cr',0)>0 else 'SELLING 🔴'})\n"
        f"DII Net: ₹{flow.get('dii_net_cr')} Cr\n"
        f"Signal: {flow.get('signal')}"
    )
    return send_alert(msg, "FII_ALERT", flow)


# ─────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────

def _send_telegram(message: str) -> tuple[bool, str]:
    if not HTTP:
        return False, "httpx not installed"
    try:
        url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = httpx.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "HTML",
        }, timeout=10)
        if resp.status_code == 200:
            return True, ""
        return False, resp.text
    except Exception as e:
        return False, str(e)


def test_telegram() -> dict:
    """Send a test message to verify Telegram setup."""
    ok, err = _send_telegram("✅ NSE AI Trading Bot connected successfully!")
    return {"success": ok, "error": err}


# ─────────────────────────────────────────────
# WHATSAPP (Twilio)
# ─────────────────────────────────────────────

def _send_whatsapp(message: str) -> tuple[bool, str]:
    if not HTTP:
        return False, "httpx not installed"
    try:
        resp = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
            auth=(TWILIO_SID, TWILIO_AUTH),
            data={"From": TWILIO_FROM, "To": TWILIO_TO, "Body": message},
            timeout=10
        )
        if resp.status_code in (200, 201):
            return True, ""
        return False, resp.text
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────

def _send_email(subject: str, body: str) -> tuple[bool, str]:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"NSE AI — {subject}"
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────
# ALERT CONFIG
# ─────────────────────────────────────────────

def get_alert_config() -> dict:
    return _get_config()


def update_alert_config(updates: dict) -> dict:
    conn = _conn()
    allowed = ["telegram","whatsapp","email","min_grade"]
    sets    = ", ".join(f"{k}=?" for k in updates if k in allowed)
    vals    = [updates[k] for k in updates if k in allowed]
    if sets:
        conn.execute(f"UPDATE alert_config SET {sets} WHERE id=1", vals)
        conn.commit()
    conn.close()
    return _get_config()


def get_alert_log(limit: int = 100) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM alert_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    cols = ["id","channel","alert_type","message","status","error","timestamp"]
    return [dict(zip(cols, r)) for r in rows]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

EMOJI = {
    "TARGET_HIT":   "🎯",
    "STOP_HIT":     "🛑",
    "NEW_SIGNAL":   "🚀",
    "NEAR_TARGET":  "⚡",
    "NEAR_STOP":    "⚠️",
    "FII_ALERT":    "🏦",
    "DAILY_SUMMARY":"📊",
    "INFO":         "ℹ️",
}

def _format_message(message: str, alert_type: str, data: dict | None) -> str:
    emoji = EMOJI.get(alert_type, "●")
    ts    = datetime.now(IST).strftime("%d %b %Y  %H:%M IST")
    return f"{emoji} <b>NSE AI</b>  [{ts}]\n\n{message}"


def _get_config() -> dict:
    conn = _conn()
    row  = conn.execute("SELECT * FROM alert_config WHERE id=1").fetchone()
    conn.close()
    if not row:
        return {"telegram":1,"whatsapp":0,"email":0,"min_grade":"HIGH"}
    cols = ["id","telegram","whatsapp","email","min_grade","alert_types"]
    d = dict(zip(cols, row))
    try:
        d["alert_types"] = json.loads(d["alert_types"])
    except Exception:
        pass
    return d


def _log_alert(channel, alert_type, message, status, error=None):
    conn = _conn()
    conn.execute("""
        INSERT INTO alert_log (channel, alert_type, message, status, error, timestamp)
        VALUES (?,?,?,?,?,?)
    """, (channel, alert_type, message[:500], status, error, datetime.now(IST).isoformat()))
    conn.commit()
    conn.close()


def _conn():
    return sqlite3.connect(DB)
