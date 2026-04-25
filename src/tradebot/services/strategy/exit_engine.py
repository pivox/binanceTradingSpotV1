from __future__ import annotations

import time
from dataclasses import replace
from decimal import Decimal
from typing import Optional

import structlog

from tradebot.config.types import StrategyConfig
from tradebot.domain.models.candle import Candle
from tradebot.domain.models.exit_intent import ExitIntent, ExitReason
from tradebot.domain.models.position import Position
from tradebot.services.mtf._conditions import _get_value

log = structlog.get_logger()

_DEFAULT_TRAILING_MULT = Decimal("2.0")
_DEFAULT_TIMEOUT_MS = 48 * 3600 * 1000  # 48h
_DEFAULT_RSI_EXTREME = 78.0


def _mark_lot_filled(position: Position, lot_id: str) -> Position:
    plan = position.exit_plan
    if lot_id == "A":
        new_lot = replace(plan.lot_a, is_filled=True, fill_time_ms=int(time.time() * 1000))
        new_plan = replace(plan, lot_a=new_lot)
    elif lot_id == "B":
        new_lot = replace(plan.lot_b, is_filled=True, fill_time_ms=int(time.time() * 1000))
        new_plan = replace(plan, lot_b=new_lot)
    else:
        new_lot = replace(plan.lot_c, is_filled=True, fill_time_ms=int(time.time() * 1000))
        new_plan = replace(plan, lot_c=new_lot)
    return replace(position, exit_plan=new_plan)


def _check_forced_exits(
    position: Position,
    snapshot_1h: dict,
    candle_5m: Candle,
    config: Optional[StrategyConfig],
) -> Optional[ExitIntent]:
    ema20_1h = _get_value(snapshot_1h, "ema20")
    ema50_1h = _get_value(snapshot_1h, "ema50")
    ema200_1h = _get_value(snapshot_1h, "ema200")
    rsi_1h = _get_value(snapshot_1h, "rsi")

    # Death cross EMA20/EMA50 sur 1h
    if ema20_1h is not None and ema50_1h is not None and ema20_1h < ema50_1h:
        return ExitIntent(
            position_id=position.id,
            lot_id="ALL",
            reason=ExitReason.FORCED_DEATH_CROSS,
            quantity=position.quantity_remaining,
            order_type="MARKET",
        )

    # Prix sous EMA200 1h
    if ema200_1h is not None and candle_5m.close < Decimal(str(ema200_1h)):
        return ExitIntent(
            position_id=position.id,
            lot_id="ALL",
            reason=ExitReason.FORCED_EMA200,
            quantity=position.quantity_remaining,
            order_type="MARKET",
        )

    # RSI 1h extrême (> 78) : sortir B et C
    rsi_limit = _DEFAULT_RSI_EXTREME
    if (
        rsi_1h is not None
        and rsi_1h > rsi_limit
        and not position.exit_plan.lot_b.is_filled
    ):
        qty = position.exit_plan.lot_b.quantity + (
            position.exit_plan.lot_c.quantity if not position.exit_plan.lot_c.is_filled else Decimal("0")
        )
        return ExitIntent(
            position_id=position.id,
            lot_id="BC",
            reason=ExitReason.FORCED_RSI_EXTREME,
            quantity=qty,
            order_type="MARKET",
        )

    # Timeout 48h sans TP A
    age_ms = candle_5m.close_time_ms - position.opened_at_ms
    if age_ms > _DEFAULT_TIMEOUT_MS and not position.exit_plan.lot_a.is_filled:
        return ExitIntent(
            position_id=position.id,
            lot_id="ALL",
            reason=ExitReason.FORCED_TIMEOUT,
            quantity=position.quantity_remaining,
            order_type="MARKET",
        )

    return None


def _update_trailing_c(
    position: Position,
    candle_5m: Candle,
    snapshot_5m: dict,
) -> list[ExitIntent]:
    if not position.exit_plan.lot_a.is_filled or position.exit_plan.lot_c.is_filled:
        return []

    atr_raw = _get_value(snapshot_5m, "atr")
    if atr_raw is None:
        return []

    atr_5m = Decimal(str(atr_raw))
    new_high = max(position.high_since_entry, candle_5m.high)
    trailing_level = new_high - atr_5m * _DEFAULT_TRAILING_MULT

    current_trailing = position.exit_plan.lot_c.current_trailing or Decimal("0")

    # Prix touche le trailing → vendre
    if candle_5m.close <= trailing_level:
        return [ExitIntent(
            position_id=position.id,
            lot_id="C",
            reason=ExitReason.TRAILING_STOP_C,
            quantity=position.exit_plan.lot_c.quantity,
            order_type="MARKET",
            new_trailing_level=trailing_level,
        )]

    # Trailing monte → mise à jour niveau (pas de vente)
    if trailing_level > current_trailing:
        return [ExitIntent(
            position_id=position.id,
            lot_id="C",
            reason=ExitReason.TRAILING_STOP_C,
            quantity=Decimal("0"),
            order_type="STOP_MARKET",
            new_trailing_level=trailing_level,
        )]

    return []


def _check_breakeven(position: Position, candle_5m: Candle) -> Optional[ExitIntent]:
    if position.exit_plan.lot_a.is_filled:
        return None
    r = position.exit_plan.r_distance
    if r <= Decimal("0"):
        return None
    current_price = candle_5m.close
    target_1r = position.entry_price + r
    target_1_5r = position.entry_price + (r * Decimal("1.5"))

    new_sl: Optional[Decimal] = None
    if current_price >= target_1_5r:
        new_sl = position.entry_price + (r * Decimal("0.5"))
    elif current_price >= target_1r:
        new_sl = position.entry_price + (r * Decimal("0.2"))

    if new_sl is not None and new_sl > position.stop_loss:
        return ExitIntent(
            position_id=position.id,
            lot_id="NONE",
            reason=ExitReason.SL_GLOBAL,
            quantity=Decimal("0"),
            order_type="STOP_MARKET",
            new_stop_loss=new_sl,
        )
    return None


def compute_exit_intents(
    position: Position,
    snapshot_1h: dict,
    snapshot_5m: dict,
    candle_5m: Candle,
    config: Optional[StrategyConfig] = None,
) -> list[ExitIntent]:
    intents: list[ExitIntent] = []

    # 1. Sorties forcées — priorité absolue
    forced = _check_forced_exits(position, snapshot_1h, candle_5m, config)
    if forced is not None:
        return [forced]

    # 2. Trailing Lot C
    trailing = _update_trailing_c(position, candle_5m, snapshot_5m)
    intents.extend(trailing)

    # 3. Breakeven
    be = _check_breakeven(position, candle_5m)
    if be is not None:
        intents.append(be)

    return intents
