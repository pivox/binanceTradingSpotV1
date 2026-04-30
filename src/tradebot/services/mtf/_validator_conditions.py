"""Conditions atomiques pour le MTF Validator (Phase 1b).

Format snapshot attendu : payload_json produit par factory.py.
  Scalaires  : {"status": "available", "value": X}
  Namespaced : macd → {"macd": {…}, "signal": {…}, "hist": {…}}
  close_price : float brut (ajouté par factory depuis la Phase 1b)

NOTE close_price : les snapshots persistés avant la Phase 1b n'ont pas ce champ.
Les conditions qui en dépendent (price_above_ema20, price_near_ema20,
close_above_recent_high, atr_contracting en fallback) retournent False si absent.
Pour le backtesting Phase 2, le caller doit injecter close_price depuis la table
candles avant d'appeler validate() :
    payload = {**snapshot.payload_json, "close_price": candle.close}
"""
from __future__ import annotations

from typing import Any


def _val(snap: dict[str, Any], key: str) -> float | None:
    f = snap.get(key)
    if isinstance(f, dict) and f.get("status") == "available":
        return float(f["value"])
    return None


def _macd_hist(snap: dict[str, Any]) -> float | None:
    macd_block = snap.get("macd")
    if not isinstance(macd_block, dict):
        return None
    hist = macd_block.get("hist")
    if isinstance(hist, dict) and hist.get("status") == "available":
        return float(hist["value"])
    return None


def _close(snap: dict[str, Any]) -> float | None:
    cp = snap.get("close_price")
    return float(cp) if cp is not None else None


# ── Conditions 4h ────────────────────────────────────────────────────────────

def ema20_above_ema50(snap: dict[str, Any], _prev: dict | None = None) -> bool:
    e20, e50 = _val(snap, "ema20"), _val(snap, "ema50")
    return e20 is not None and e50 is not None and e20 > e50


def ema50_above_ema200(snap: dict[str, Any], _prev: dict | None = None) -> bool:
    e50, e200 = _val(snap, "ema50"), _val(snap, "ema200")
    return e50 is not None and e200 is not None and e50 > e200


def rsi_between_45_70(snap: dict[str, Any], _prev: dict | None = None) -> bool:
    rsi = _val(snap, "rsi")
    return rsi is not None and 45.0 <= rsi <= 70.0


def macd_hist_positive(snap: dict[str, Any], _prev: dict | None = None) -> bool:
    hist = _macd_hist(snap)
    return hist is not None and hist > 0.0


# ── Conditions 1h ────────────────────────────────────────────────────────────

def price_above_ema20(snap: dict[str, Any], _prev: dict | None = None) -> bool:
    close = _close(snap)
    ema20 = _val(snap, "ema20")
    return close is not None and ema20 is not None and close > ema20


def adx_gt_25(snap: dict[str, Any], _prev: dict | None = None) -> bool:
    adx = _val(snap, "adx")
    return adx is not None and adx > 25.0


def macd_hist_positive_or_rising(snap: dict[str, Any], prev: dict | None = None) -> bool:
    hist = _macd_hist(snap)
    if hist is None:
        return False
    if hist > 0.0:
        return True
    if prev is not None:
        prev_hist = _macd_hist(prev)
        return prev_hist is not None and hist > prev_hist
    return False


# ── Conditions 15m ───────────────────────────────────────────────────────────

def rsi_between_40_60(snap: dict[str, Any], _prev: dict | None = None) -> bool:
    rsi = _val(snap, "rsi")
    return rsi is not None and 40.0 <= rsi <= 60.0


def price_near_ema20(snap: dict[str, Any], _prev: dict | None = None, tolerance: float = 0.015) -> bool:
    close = _close(snap)
    ema20 = _val(snap, "ema20")
    if close is None or ema20 is None or ema20 == 0.0:
        return False
    return abs(close - ema20) / ema20 <= tolerance


def atr_contracting(snap: dict[str, Any], prev: dict | None = None) -> bool:
    atr = _val(snap, "atr")
    if atr is None:
        return False
    if prev is not None:
        prev_atr = _val(prev, "atr")
        if prev_atr is not None and prev_atr > 0.0:
            return atr < prev_atr
    # Sans snapshot précédent : ATR < 2% du prix (consolidation)
    close = _close(snap)
    if close is None or close == 0.0:
        return False
    return (atr / close) < 0.02


# ── Trigger 5m ───────────────────────────────────────────────────────────────

def macd_hist_turning_positive(snap: dict[str, Any], prev: dict | None = None) -> bool:
    hist = _macd_hist(snap)
    if hist is None or hist <= 0.0:
        return False
    if prev is not None:
        prev_hist = _macd_hist(prev)
        if prev_hist is not None:
            return prev_hist <= 0.0 and hist > 0.0
    return hist > 0.0


def close_above_recent_high(snap: dict[str, Any], _prev: dict | None = None) -> bool:
    """Proxy : close > EMA50 (breakout de la structure récente)."""
    close = _close(snap)
    ema50 = _val(snap, "ema50")
    return close is not None and ema50 is not None and close > ema50


# ── Filtres bloquants ────────────────────────────────────────────────────────

def rsi_4h_gt_75(snaps: dict[str, dict], _prev: dict | None = None) -> bool:
    rsi = _val(snaps.get("4h", {}), "rsi")
    return rsi is not None and rsi > 75.0


def price_4h_gt_ema20_plus_2atr(snaps: dict[str, dict], _prev: dict | None = None) -> bool:
    snap = snaps.get("4h", {})
    close = _close(snap)
    ema20 = _val(snap, "ema20")
    atr = _val(snap, "atr")
    if close is None or ema20 is None or atr is None:
        return False
    return close > ema20 + 2.0 * atr


def adx_1h_lt_20(snaps: dict[str, dict], _prev: dict | None = None) -> bool:
    adx = _val(snaps.get("1h", {}), "adx")
    return adx is not None and adx < 20.0


def macd_1h_hist_negative_and_falling(
    snaps: dict[str, dict],
    prev_snaps: dict[str, dict] | None = None,
) -> bool:
    hist = _macd_hist(snaps.get("1h", {}))
    if hist is None or hist >= 0.0:
        return False
    if prev_snaps is None:
        return False  # pas de confirmation de la baisse sans snapshot précédent
    prev_hist = _macd_hist(prev_snaps.get("1h", {}))
    if prev_hist is None:
        return False
    return hist < prev_hist  # plus négatif qu'avant → en baisse
