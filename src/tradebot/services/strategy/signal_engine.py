from __future__ import annotations

import structlog
from decimal import Decimal
from typing import Optional

from tradebot.config.types import StrategyConfig
from tradebot.domain.models.candle import Candle
from tradebot.domain.models.cascade_result import CascadeResult
from tradebot.domain.models.signal import Signal, SignalQuality, SetupType
from tradebot.domain.models.symbol_filters import SymbolFilters
from tradebot.infra.binance.filters import BinanceFilters
from tradebot.services.mtf._conditions import _get_value, stochrsi_bullish, volume_above_average

log = structlog.get_logger()

_DEFAULT_SL_ATR_MULT = Decimal("1.5")
_DEFAULT_SIGNAL_EXPIRY_BARS = 15  # bougies 1m = 15 minutes


def _risk_pct(cascade: CascadeResult, base_pct: float = 0.01) -> float:
    pct = base_pct
    if cascade.quality == SignalQuality.MEDIUM:
        pct *= 0.6
    if cascade.active_setup == SetupType.C:
        pct *= 0.7
    if cascade.active_setup == SetupType.D:
        pct *= 0.5
    return pct


def _tp_at_d(entry: Decimal, r: Decimal) -> Decimal:
    """Setup D utilise TP Lot A = 1.5R (tendance non établie)."""
    return entry + (r * Decimal("1.5"))


def compute_signal(
    cascade: CascadeResult,
    candle_1m: Candle,
    snapshot_1m: dict,
    snapshot_5m: dict,
    filters: SymbolFilters,
    prev_candle_1m: Optional[Candle] = None,
    config: Optional[StrategyConfig] = None,
) -> Optional[Signal]:
    expiry_ms = cascade.evaluated_at_ms + (_DEFAULT_SIGNAL_EXPIRY_BARS * 60 * 1000)
    if candle_1m.close_time_ms > expiry_ms:
        return None  # signal expiré

    # Vérification du trigger 1m (au moins 2/3 conditions)
    trigger_conditions = [
        # Micro-breakout : close > high de la bougie précédente
        (prev_candle_1m is not None and candle_1m.close > prev_candle_1m.high),
        # Volume 1m > 1.5× la moyenne
        volume_above_average(snapshot_1m, 1.5),
        # StochRSI 5m bullish
        stochrsi_bullish(snapshot_5m, max_k=0.75),
    ]
    if sum(trigger_conditions) < 2:
        return None

    # ATR 1m pour le SL
    atr_raw = _get_value(snapshot_1m, "atr")
    if atr_raw is None:
        return None
    atr_1m = Decimal(str(atr_raw))

    # Entry = close 1m + léger slippage
    entry_raw = candle_1m.close * Decimal("1.0005")

    # SL = min(recent_low × 0.999, entry - 1.5×ATR)
    atr_sl = entry_raw - (atr_1m * _DEFAULT_SL_ATR_MULT)
    sl_from_low = candle_1m.low * Decimal("0.999")
    stop_loss_raw = min(sl_from_low, atr_sl)

    r = entry_raw - stop_loss_raw
    if r <= Decimal("0"):
        log.warning("signal_invalid_r", symbol=cascade.symbol, r=str(r))
        return None

    # TP selon setup
    if cascade.active_setup == SetupType.D:
        tp_a_raw = _tp_at_d(entry_raw, r)
    else:
        tp_a_raw = entry_raw + (r * Decimal("2"))
    tp_b_raw = entry_raw + (r * Decimal("3"))

    # Arrondi Binance
    entry_price = BinanceFilters.round_price(entry_raw, filters)
    stop_loss = BinanceFilters.round_price(stop_loss_raw, filters)
    tp_lot_a = BinanceFilters.round_price(tp_a_raw, filters)
    tp_lot_b = BinanceFilters.round_price(tp_b_raw, filters)

    if entry_price <= stop_loss:
        return None

    base_risk = config.per_trade_quote_budget / 100 if config else 0.01
    risk_pct = _risk_pct(cascade, base_pct=0.01)

    return Signal(
        symbol=cascade.symbol,
        setup=cascade.active_setup,
        quality=cascade.quality,
        score=cascade.score,
        entry_price=entry_price,
        stop_loss=stop_loss,
        tp_lot_a=tp_lot_a,
        tp_lot_b=tp_lot_b,
        r_distance=entry_price - stop_loss,
        atr_1m=atr_1m,
        risk_pct=risk_pct,
        cascade_score=cascade.score,
        created_at_ms=candle_1m.close_time_ms,
        expires_at_ms=expiry_ms,
        trigger_candle_open_ms=candle_1m.open_time_ms,
    )
