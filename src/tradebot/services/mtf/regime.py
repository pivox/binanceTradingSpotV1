from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

from tradebot.domain.models.cascade_result import MarketRegime
from tradebot.services.mtf._conditions import (
    adx_above,
    atr_ratio,
    bollinger_squeeze,
    ema_triple_aligned_down,
    ema_triple_aligned_up,
    _get_value,
)

log = structlog.get_logger()


@dataclass(frozen=True)
class RegimeResult:
    regime: MarketRegime
    adx: float
    atr_ratio_value: float
    ema_aligned: bool
    golden_cross_detected: bool
    bb_squeeze: bool
    tradeable: bool


def _detect_golden_cross(snap_now: dict, snap_prev: Optional[dict]) -> bool:
    if snap_prev is None:
        return False
    e20_now = _get_value(snap_now, "ema20")
    e50_now = _get_value(snap_now, "ema50")
    e20_prev = _get_value(snap_prev, "ema20")
    e50_prev = _get_value(snap_prev, "ema50")
    if any(v is None for v in [e20_now, e50_now, e20_prev, e50_prev]):
        return False
    return e20_prev <= e50_prev and e20_now > e50_now


def detect_regime(
    snapshot_1h: dict,
    prev_snapshot_1h: Optional[dict] = None,
) -> RegimeResult:
    # Valeurs observées
    adx_val = _get_value(snapshot_1h, "adx") or 0.0
    close = snapshot_1h.get("close_price") or 0.0
    atr_r = atr_ratio(snapshot_1h, float(close)) if close else 0.0
    ema_up = ema_triple_aligned_up(snapshot_1h)
    ema_down = ema_triple_aligned_down(snapshot_1h)
    golden_cross = _detect_golden_cross(snapshot_1h, prev_snapshot_1h)
    squeeze = bollinger_squeeze(snapshot_1h)

    # Classement prioritaire
    if atr_r > 0.04:
        regime = MarketRegime.VOLATILE
    elif ema_down and adx_val > 25:
        regime = MarketRegime.TRENDING_DOWN
    elif golden_cross:
        regime = MarketRegime.RECOVERY
    elif ema_up and adx_val > 25:
        regime = MarketRegime.TRENDING_UP
    elif adx_val < 20:
        regime = MarketRegime.RANGING
    else:
        regime = MarketRegime.RANGING

    tradeable = regime not in (MarketRegime.VOLATILE, MarketRegime.TRENDING_DOWN)

    return RegimeResult(
        regime=regime,
        adx=adx_val,
        atr_ratio_value=atr_r,
        ema_aligned=ema_up,
        golden_cross_detected=golden_cross,
        bb_squeeze=squeeze,
        tradeable=tradeable,
    )
