"""
smart_money.py — Strike-level OI analysis, buildup detection, support/resistance
"""

import pandas as pd


# ─────────────────────────────────────────────
# CORE ANALYSIS
# ─────────────────────────────────────────────

def analyze(ce: pd.DataFrame, pe: pd.DataFrame) -> dict:
    """
    Full smart-money analysis.
    Returns PCR, bias, support, resistance, buildup signals.
    """
    ce = _clean(ce)
    pe = _clean(pe)

    pcr_data   = _pcr(ce, pe)
    levels     = _key_levels(ce, pe)
    buildups   = _buildup(ce, pe)
    bias       = _market_bias(pcr_data["pcr"], levels, buildups)
    score      = _smart_score(pcr_data["pcr"], bias)

    return {
        "pcr":        pcr_data["pcr"],
        "ce_oi_total": pcr_data["ce_total"],
        "pe_oi_total": pcr_data["pe_total"],
        "support":    levels["support"],
        "resistance": levels["resistance"],
        "max_pain":   levels["max_pain"],
        "bias":       bias,
        "signal":     bias,          # backward-compat alias
        "score":      score,
        "buildups":   buildups,
    }


# ─────────────────────────────────────────────
# SUPPORT / RESISTANCE FROM OI
# ─────────────────────────────────────────────

def get_levels(ce: pd.DataFrame, pe: pd.DataFrame) -> dict:
    """Dedicated endpoint payload for /levels."""
    ce = _clean(ce)
    pe = _clean(pe)
    return _key_levels(ce, pe)


# ─────────────────────────────────────────────
# INTERNALS
# ─────────────────────────────────────────────

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    needed = {"strikePrice", "openInterest", "changeinOpenInterest",
              "totalTradedVolume", "impliedVolatility"}
    for col in needed:
        if col not in df.columns:
            df[col] = 0
    df["strikePrice"]          = pd.to_numeric(df["strikePrice"], errors="coerce")
    df["openInterest"]         = pd.to_numeric(df["openInterest"], errors="coerce").fillna(0)
    df["changeinOpenInterest"] = pd.to_numeric(df["changeinOpenInterest"], errors="coerce").fillna(0)
    df["totalTradedVolume"]    = pd.to_numeric(df["totalTradedVolume"], errors="coerce").fillna(0)
    return df.dropna(subset=["strikePrice"])


def _pcr(ce: pd.DataFrame, pe: pd.DataFrame) -> dict:
    ce_oi = ce["openInterest"].sum()
    pe_oi = pe["openInterest"].sum()
    return {
        "pcr":      round(pe_oi / ce_oi, 3) if ce_oi else 0,
        "ce_total": int(ce_oi),
        "pe_total": int(pe_oi),
    }


def _key_levels(ce: pd.DataFrame, pe: pd.DataFrame) -> dict:
    """
    Resistance  = strike with highest CE OI  (call writers defend this)
    Support     = strike with highest PE OI  (put writers defend this)
    Max pain    = strike where total OI loss for option buyers is minimised
    """
    resistance_row = ce.loc[ce["openInterest"].idxmax()]
    support_row    = pe.loc[pe["openInterest"].idxmax()]

    resistance = int(resistance_row["strikePrice"])
    support    = int(support_row["strikePrice"])

    # ── max pain ──────────────────────────────
    strikes = sorted(set(ce["strikePrice"]) | set(pe["strikePrice"]))
    pain    = {}
    for s in strikes:
        ce_loss = ce.apply(lambda r: max(0, s - r["strikePrice"]) * r["openInterest"], axis=1).sum()
        pe_loss = pe.apply(lambda r: max(0, r["strikePrice"] - s) * r["openInterest"], axis=1).sum()
        pain[s] = ce_loss + pe_loss
    max_pain = int(min(pain, key=pain.get)) if pain else 0

    # ── top 3 CE / PE strikes by OI ──────────
    top_ce = (ce.nlargest(3, "openInterest")
                .set_index("strikePrice")["openInterest"]
                .to_dict())
    top_pe = (pe.nlargest(3, "openInterest")
                .set_index("strikePrice")["openInterest"]
                .to_dict())

    return {
        "support":    support,
        "resistance": resistance,
        "max_pain":   max_pain,
        "top_ce_strikes": {int(k): int(v) for k, v in top_ce.items()},
        "top_pe_strikes": {int(k): int(v) for k, v in top_pe.items()},
    }


def _buildup(ce: pd.DataFrame, pe: pd.DataFrame) -> list[dict]:
    """
    Classify each significant strike as one of:
      LONG_BUILDUP   — price ↑, OI ↑        (fresh longs)
      SHORT_BUILDUP  — price ↓, OI ↑        (fresh shorts)
      LONG_UNWIND    — price ↓, OI ↓        (longs exiting)
      SHORT_COVER    — price ↑, OI ↓        (shorts covering)

    For options we use OI change vs volume as proxy for direction.
    """
    results = []

    def classify(row, side: str):
        oi_chg = row["changeinOpenInterest"]
        vol    = row["totalTradedVolume"]
        if oi_chg > 0 and vol > 0:
            tag = "LONG_BUILDUP"  if side == "PE" else "SHORT_BUILDUP"
        elif oi_chg > 0 and vol <= 0:
            tag = "SHORT_BUILDUP" if side == "PE" else "LONG_BUILDUP"
        elif oi_chg < 0 and vol > 0:
            tag = "SHORT_COVER"   if side == "PE" else "LONG_UNWIND"
        else:
            tag = "LONG_UNWIND"   if side == "PE" else "SHORT_COVER"
        return tag

    threshold_ce = ce["openInterest"].quantile(0.75)
    threshold_pe = pe["openInterest"].quantile(0.75)

    for _, row in ce[ce["openInterest"] >= threshold_ce].iterrows():
        results.append({
            "strike": int(row["strikePrice"]),
            "type": "CE",
            "oi": int(row["openInterest"]),
            "oi_change": int(row["changeinOpenInterest"]),
            "buildup": classify(row, "CE"),
        })

    for _, row in pe[pe["openInterest"] >= threshold_pe].iterrows():
        results.append({
            "strike": int(row["strikePrice"]),
            "type": "PE",
            "oi": int(row["openInterest"]),
            "oi_change": int(row["changeinOpenInterest"]),
            "buildup": classify(row, "PE"),
        })

    return sorted(results, key=lambda x: x["oi"], reverse=True)[:10]


def _market_bias(pcr: float, levels: dict, buildups: list) -> str:
    score = 0

    # PCR weight
    if pcr > 1.3:
        score += 2
    elif pcr > 1.1:
        score += 1
    elif pcr < 0.7:
        score -= 2
    elif pcr < 0.9:
        score -= 1

    # Buildup weight
    bullish_tags = {"LONG_BUILDUP", "SHORT_COVER"}
    bearish_tags = {"SHORT_BUILDUP", "LONG_UNWIND"}
    for b in buildups:
        if b["buildup"] in bullish_tags:
            score += 0.5
        elif b["buildup"] in bearish_tags:
            score -= 0.5

    if score >= 2:
        return "BULLISH"
    elif score <= -2:
        return "BEARISH"
    else:
        return "RANGE"


def _smart_score(pcr: float, bias: str) -> float:
    """Normalised 0–3 contribution to conviction score."""
    if bias == "BULLISH":
        return min(3.0, round(1.0 + (pcr - 1.0) * 2, 2))
    elif bias == "BEARISH":
        return 0.0
    else:
        return 1.0
