"""Helpers atomiques pour l'évaluation des conditions d'indicateurs."""
from __future__ import annotations

from typing import Optional


def _get_value(snap: dict, key: str) -> Optional[float]:
    """Retourne la valeur si status='available', None sinon."""
    field = snap.get(key, {})
    if isinstance(field, dict) and field.get("status") == "available":
        return field.get("value")
    return None


def _get_close(snap: dict) -> Optional[float]:
    return _get_value(snap, "close") or snap.get("close_price")


def ema_aligned_up(snap: dict, fast: str, slow: str) -> bool:
    f, s = _get_value(snap, fast), _get_value(snap, slow)
    return f is not None and s is not None and f > s


def ema_triple_aligned_up(snap: dict) -> bool:
    e20, e50, e200 = (
        _get_value(snap, "ema20"),
        _get_value(snap, "ema50"),
        _get_value(snap, "ema200"),
    )
    return e20 is not None and e50 is not None and e200 is not None and e20 > e50 > e200


def ema_triple_aligned_down(snap: dict) -> bool:
    e20, e50, e200 = (
        _get_value(snap, "ema20"),
        _get_value(snap, "ema50"),
        _get_value(snap, "ema200"),
    )
    return e20 is not None and e50 is not None and e200 is not None and e20 < e50 < e200


def price_above_ema(snap: dict, ema_key: str) -> bool:
    close = _get_value(snap, "close") or snap.get("close_price")
    ema = _get_value(snap, ema_key)
    # Essaie de lire le prix du snapshot (dernier close)
    if close is None:
        return False
    return ema is not None and float(close) > float(ema)


def price_above_vwap(snap: dict) -> bool:
    vwap = _get_value(snap, "vwap")
    close = snap.get("close_price") or _get_value(snap, "close")
    if close is None or vwap is None:
        return False
    return float(close) > float(vwap)


def adx_above(snap: dict, threshold: float = 20.0) -> bool:
    adx = _get_value(snap, "adx")
    return adx is not None and adx > threshold


def adx_trending_up(snap: dict) -> bool:
    adx_data = snap.get("adx", {})
    if not isinstance(adx_data, dict) or adx_data.get("status") != "available":
        return False
    value = adx_data.get("value", 0)
    plus_di = adx_data.get("plus_di", 0)
    minus_di = adx_data.get("minus_di", 0)
    return value > 20 and plus_di > minus_di


def rsi_above(snap: dict, threshold: float) -> bool:
    rsi = _get_value(snap, "rsi")
    return rsi is not None and rsi > threshold


def rsi_in_range(snap: dict, low: float, high: float) -> bool:
    rsi = _get_value(snap, "rsi")
    return rsi is not None and low <= rsi <= high


def rsi_not_overbought(snap: dict, limit: float = 70.0) -> bool:
    rsi = _get_value(snap, "rsi")
    return rsi is None or rsi < limit


def macd_positive(snap: dict) -> bool:
    macd_data = snap.get("macd", {})
    if not isinstance(macd_data, dict) or macd_data.get("status") != "available":
        return False
    return macd_data.get("value", -1) > 0


def macd_positive_or_crossing(snap: dict) -> bool:
    macd_data = snap.get("macd", {})
    if not isinstance(macd_data, dict) or macd_data.get("status") != "available":
        return False
    macd_line = macd_data.get("value", -1)
    signal_line = macd_data.get("signal", -1)
    histogram = macd_data.get("histogram", -1)
    return macd_line > 0 or (histogram > 0 and macd_line > signal_line)


def macd_histogram_positive(snap: dict) -> bool:
    macd_data = snap.get("macd", {})
    if not isinstance(macd_data, dict) or macd_data.get("status") != "available":
        return False
    return macd_data.get("histogram", -1) > 0


def bollinger_squeeze(snap: dict, threshold: float = 0.03) -> bool:
    bb = snap.get("bollinger", {})
    if not isinstance(bb, dict) or bb.get("status") != "available":
        return False
    bandwidth = bb.get("bandwidth", 1.0)
    return bandwidth < threshold


def price_above_upper_bb(snap: dict) -> bool:
    bb = snap.get("bollinger", {})
    if not isinstance(bb, dict) or bb.get("status") != "available":
        return False
    close = snap.get("close_price")
    upper = bb.get("upper")
    if close is None or upper is None:
        return False
    return float(close) > float(upper)


def price_between_ema20_ema50(snap: dict) -> bool:
    """Prix en pullback : entre EMA20 et EMA50."""
    close = snap.get("close_price")
    e20 = _get_value(snap, "ema20")
    e50 = _get_value(snap, "ema50")
    if close is None or e20 is None or e50 is None:
        return False
    c = float(close)
    return min(e20, e50) <= c <= max(e20, e50)


def stochrsi_crossing_up(snap: dict, max_k: float = 0.30) -> bool:
    sr = snap.get("stoch_rsi", {})
    if not isinstance(sr, dict) or sr.get("status") != "available":
        return False
    k = sr.get("k", 1.0)
    d = sr.get("d", 1.0)
    return k < max_k and k > d


def stochrsi_bullish(snap: dict, max_k: float = 0.75) -> bool:
    sr = snap.get("stoch_rsi", {})
    if not isinstance(sr, dict) or sr.get("status") != "available":
        return False
    k = sr.get("k", 1.0)
    d = sr.get("d", 1.0)
    return k < max_k and k > d


def price_near_pivot(snap: dict, tolerance: float = 0.002) -> bool:
    pivots = snap.get("pivots", {})
    if not isinstance(pivots, dict) or pivots.get("status") != "available":
        return False
    close = snap.get("close_price")
    if close is None:
        return False
    c = float(close)
    for key in ("s1", "s2", "pp"):
        level = pivots.get(key)
        if level and abs(c - float(level)) / float(level) <= tolerance:
            return True
    return False


def volume_above_average(snap: dict, multiplier: float = 1.0) -> bool:
    vol_data = snap.get("volume_ratio")
    if vol_data is None:
        return False
    return float(vol_data) >= multiplier


def atr_ratio(snap: dict, close_price: float) -> float:
    atr = _get_value(snap, "atr")
    if atr is None or close_price == 0:
        return 0.0
    return atr / close_price
