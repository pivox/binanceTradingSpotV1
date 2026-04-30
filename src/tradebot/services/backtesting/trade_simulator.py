from __future__ import annotations

from typing import Any, Literal

from tradebot.domain.models.candle import Candle
from tradebot.services.backtesting.models import BacktestConfig


def _get_available(snap: dict[str, Any], key: str) -> float | None:
    entry = snap.get(key)
    if not isinstance(entry, dict):
        return None
    if entry.get("status") != "available":
        return None
    v = entry.get("value")
    return float(v) if v is not None else None


def compute_sl_tp(
    entry_price: float,
    snap_5m: dict[str, Any],
    config: BacktestConfig,
) -> tuple[float, float, Literal["PIVOT", "ATR_FALLBACK"]]:
    """
    Returns (stop_loss, take_profit, sl_method).

    Priority: pivot S1/S2 support + buffer (max 2%). Fallback: ATR × k.
    """
    pivots = snap_5m.get("pivots")
    s1 = _get_available(pivots, "s1") if isinstance(pivots, dict) else None
    s2 = _get_available(pivots, "s2") if isinstance(pivots, dict) else None

    candidates = [v for v in [s1, s2] if v is not None and v < entry_price]
    if candidates:
        closest_support = max(candidates)
        sl_raw = closest_support * (1.0 - config.sl_buffer_pct)
        dist_pct = (entry_price - sl_raw) / entry_price
        if dist_pct <= config.max_sl_pct:
            tp = entry_price + (entry_price - sl_raw) * config.r_multiple
            return sl_raw, tp, "PIVOT"

    atr_val = _get_available(snap_5m, "atr")
    if atr_val is not None and atr_val > 0:
        sl_raw = entry_price - atr_val * config.k_atr
        dist_pct = (entry_price - sl_raw) / entry_price
        if dist_pct > config.max_sl_pct:
            sl_raw = entry_price * (1.0 - config.max_sl_pct)
        tp = entry_price + (entry_price - sl_raw) * config.r_multiple
        return sl_raw, tp, "ATR_FALLBACK"

    raise ValueError(
        f"cannot compute SL: no pivot support below {entry_price} and ATR unavailable"
    )


def simulate_exit(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    candles_after_entry: list[Candle],
) -> tuple[int | None, float | None, Literal["TP", "SL", "OPEN"], float, float]:
    """
    Walk forward through candles to find the first SL or TP hit.

    Returns (exit_time_ms, exit_price, exit_reason, mfe_pct, mae_pct).
    Gap-aware and pessimistic: a candle that opens through SL exits at open price
    (not at stop_loss), and SL is checked before TP within the same candle.
    """
    mfe_pct = 0.0
    mae_pct = 0.0

    for candle in candles_after_entry:
        open_p = float(candle.open)
        high = float(candle.high)
        low = float(candle.low)

        mfe_pct = max(mfe_pct, (high - entry_price) / entry_price * 100.0)
        mae_pct = max(mae_pct, (entry_price - low) / entry_price * 100.0)

        # Gap at open (pessimistic: SL first)
        if open_p <= stop_loss:
            return candle.close_time_ms, open_p, "SL", mfe_pct, mae_pct
        if open_p >= take_profit:
            return candle.close_time_ms, open_p, "TP", mfe_pct, mae_pct

        # Intra-candle (pessimistic: SL first)
        if low <= stop_loss:
            return candle.close_time_ms, stop_loss, "SL", mfe_pct, mae_pct
        if high >= take_profit:
            return candle.close_time_ms, take_profit, "TP", mfe_pct, mae_pct

    return None, None, "OPEN", mfe_pct, mae_pct
