"""Unit tests for exit engine (compute_exit_intents)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from tradebot.domain.models.candle import Candle
from tradebot.domain.models.exit_intent import ExitReason
from tradebot.domain.models.exit_plan import ExitPlan, Lot, LotRule
from tradebot.domain.models.position import Position, PositionStatus
from tradebot.services.strategy.exit_engine import compute_exit_intents


# ── Helpers ───────────────────────────────────────────────────────────────────

def _av(value: float) -> dict:
    return {"status": "available", "value": value}


def _adx_av(value: float, plus_di: float = 30.0, minus_di: float = 5.0) -> dict:
    return {"status": "available", "value": value, "plus_di": plus_di, "minus_di": minus_di}


def _lot(lot_id: str, pct: float, qty: float, is_filled: bool = False) -> Lot:
    return Lot(
        id=lot_id,
        pct=pct,
        rule=LotRule(type="tp_r_multiple", r_multiple=2.0 if lot_id == "A" else 3.0),
        quantity=Decimal(str(qty)),
        is_filled=is_filled,
    )


def _exit_plan(
    r: float = 100.0,
    lot_a_filled: bool = False,
    lot_b_filled: bool = False,
    lot_c_filled: bool = False,
) -> ExitPlan:
    return ExitPlan(
        lot_a=_lot("A", 0.60, 0.006, lot_a_filled),
        lot_b=_lot("B", 0.30, 0.003, lot_b_filled),
        lot_c=_lot("C", 0.10, 0.001, lot_c_filled),
        r_distance=Decimal(str(r)),
    )


def _position(
    entry: float = 10_000.0,
    sl: float = 9_900.0,
    high: float = 10_000.0,
    opened_at_ms: int = 0,
    lot_a_filled: bool = False,
    lot_b_filled: bool = False,
    lot_c_filled: bool = False,
) -> Position:
    r = entry - sl
    return Position(
        id="pos-001",
        symbol="BTCUSDC",
        side="BUY",
        status=PositionStatus.ACTIVE,
        entry_price=Decimal(str(entry)),
        quantity_total=Decimal("0.01"),
        stop_loss=Decimal(str(sl)),
        atr_at_entry=Decimal("80.0"),
        signal_score=0.78,
        setup_type="A",
        shard_id=0,
        opened_at_ms=opened_at_ms,
        exit_plan=_exit_plan(r=r, lot_a_filled=lot_a_filled, lot_b_filled=lot_b_filled, lot_c_filled=lot_c_filled),
        high_since_entry=Decimal(str(high)),
    )


def _candle(close: float, high: float = 0.0, close_time_ms: int = 1_000_000) -> Candle:
    return Candle(
        symbol="BTCUSDC",
        timeframe="5m",
        open_time_ms=close_time_ms - 300_000,
        close_time_ms=close_time_ms,
        open=Decimal(str(close - 10)),
        high=Decimal(str(high or close + 20)),
        low=Decimal(str(close - 20)),
        close=Decimal(str(close)),
        volume=Decimal("100"),
    )


def _snapshot_1h(ema20: float = 105.0, ema50: float = 100.0, ema200: float = 90.0, rsi: float = 55.0) -> dict:
    return {
        "ema20": _av(ema20),
        "ema50": _av(ema50),
        "ema200": _av(ema200),
        "rsi": _av(rsi),
        "adx": _adx_av(25.0),
    }


def _snapshot_5m(atr: float = 50.0) -> dict:
    return {"atr": _av(atr)}


# ── Forced exit: death cross ──────────────────────────────────────────────────

class TestForcedDeathCross:
    def test_exits_all_when_ema20_below_ema50(self) -> None:
        pos = _position()
        snap_1h = _snapshot_1h(ema20=95.0, ema50=100.0)  # death cross
        intents = compute_exit_intents(pos, snap_1h, _snapshot_5m(), _candle(10_050.0))
        assert len(intents) == 1
        assert intents[0].lot_id == "ALL"
        assert intents[0].reason == ExitReason.FORCED_DEATH_CROSS
        assert intents[0].order_type == "MARKET"

    def test_death_cross_ignores_rsi_and_trailing(self) -> None:
        # Even with extreme RSI, death cross takes priority
        pos = _position()
        snap_1h = _snapshot_1h(ema20=90.0, ema50=100.0, rsi=82.0)
        intents = compute_exit_intents(pos, snap_1h, _snapshot_5m(), _candle(10_050.0))
        assert intents[0].reason == ExitReason.FORCED_DEATH_CROSS


# ── Forced exit: EMA200 ───────────────────────────────────────────────────────

class TestForcedEma200:
    def test_exits_all_when_price_below_ema200(self) -> None:
        pos = _position(entry=10_000.0)
        snap_1h = _snapshot_1h(ema20=105.0, ema50=100.0, ema200=10_100.0)
        candle = _candle(9_950.0)  # below EMA200
        intents = compute_exit_intents(pos, snap_1h, _snapshot_5m(), candle)
        assert intents[0].reason == ExitReason.FORCED_EMA200
        assert intents[0].lot_id == "ALL"

    def test_no_exit_when_price_above_ema200(self) -> None:
        pos = _position(entry=10_000.0)
        snap_1h = _snapshot_1h(ema200=9_500.0)  # price well above
        intents = compute_exit_intents(pos, snap_1h, _snapshot_5m(), _candle(10_050.0))
        assert not any(i.reason == ExitReason.FORCED_EMA200 for i in intents)


# ── Forced exit: RSI extreme ──────────────────────────────────────────────────

class TestForcedRsiExtreme:
    def test_exits_bc_when_rsi_above_78(self) -> None:
        pos = _position()
        snap_1h = _snapshot_1h(rsi=80.0)
        intents = compute_exit_intents(pos, snap_1h, _snapshot_5m(), _candle(10_200.0))
        assert len(intents) == 1
        assert intents[0].lot_id == "BC"
        assert intents[0].reason == ExitReason.FORCED_RSI_EXTREME

    def test_no_rsi_exit_when_lot_b_already_filled(self) -> None:
        pos = _position(lot_b_filled=True)
        snap_1h = _snapshot_1h(rsi=82.0)
        intents = compute_exit_intents(pos, snap_1h, _snapshot_5m(), _candle(10_200.0))
        assert not any(i.reason == ExitReason.FORCED_RSI_EXTREME for i in intents)

    def test_no_rsi_exit_when_rsi_below_threshold(self) -> None:
        pos = _position()
        snap_1h = _snapshot_1h(rsi=75.0)
        intents = compute_exit_intents(pos, snap_1h, _snapshot_5m(), _candle(10_200.0))
        assert not any(i.reason == ExitReason.FORCED_RSI_EXTREME for i in intents)


# ── Forced exit: timeout ──────────────────────────────────────────────────────

class TestForcedTimeout:
    def test_exits_all_after_48h_without_lot_a(self) -> None:
        opened_at_ms = 0
        candle_close_ms = 48 * 3600 * 1000 + 1  # just over 48h
        pos = _position(opened_at_ms=opened_at_ms)
        candle = _candle(10_050.0, close_time_ms=candle_close_ms)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(), candle)
        assert intents[0].reason == ExitReason.FORCED_TIMEOUT
        assert intents[0].lot_id == "ALL"

    def test_no_timeout_if_lot_a_already_filled(self) -> None:
        pos = _position(opened_at_ms=0, lot_a_filled=True)
        candle = _candle(10_050.0, close_time_ms=49 * 3600 * 1000)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(), candle)
        assert not any(i.reason == ExitReason.FORCED_TIMEOUT for i in intents)


# ── Trailing stop Lot C ───────────────────────────────────────────────────────

class TestTrailingLotC:
    def test_no_trailing_before_lot_a_filled(self) -> None:
        pos = _position(high=10_200.0)  # lot A not filled
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(atr=50.0), _candle(10_050.0))
        assert not any(i.reason == ExitReason.TRAILING_STOP_C for i in intents)

    def test_trailing_fires_when_price_hits_level(self) -> None:
        # Entry 10000, high 10400, ATR 50 → trailing = 10400 - 2*50 = 10300
        # Close at 10250 (below 10300) → should trigger sell
        pos = _position(entry=10_000.0, high=10_400.0, lot_a_filled=True)
        candle = _candle(close=10_250.0, high=10_400.0)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(atr=50.0), candle)
        sell = [i for i in intents if i.reason == ExitReason.TRAILING_STOP_C and i.quantity > 0]
        assert len(sell) == 1
        assert sell[0].lot_id == "C"
        assert sell[0].order_type == "MARKET"

    def test_trailing_update_when_new_high_no_sell(self) -> None:
        # New high but price still above trailing → only update level
        pos = _position(entry=10_000.0, high=10_200.0, lot_a_filled=True)
        candle = _candle(close=10_450.0, high=10_500.0)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(atr=50.0), candle)
        updates = [i for i in intents if i.reason == ExitReason.TRAILING_STOP_C and i.quantity == 0]
        assert len(updates) == 1
        assert updates[0].new_trailing_level is not None

    def test_no_trailing_when_lot_c_filled(self) -> None:
        pos = _position(lot_a_filled=True, lot_c_filled=True)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(atr=50.0), _candle(10_300.0))
        assert not any(i.reason == ExitReason.TRAILING_STOP_C for i in intents)


# ── Breakeven ─────────────────────────────────────────────────────────────────

class TestBreakeven:
    def test_sl_moves_at_1r(self) -> None:
        # Entry 10000, SL 9900 → R=100, 1R target = 10100
        # Price at 10150 (> 10100) → should move SL up
        pos = _position(entry=10_000.0, sl=9_900.0)
        candle = _candle(10_150.0)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(), candle)
        be = [i for i in intents if i.reason == ExitReason.SL_GLOBAL]
        assert len(be) == 1
        assert be[0].new_stop_loss is not None
        assert be[0].new_stop_loss > Decimal("9900")
        assert be[0].quantity == Decimal("0")

    def test_sl_moves_further_at_1_5r(self) -> None:
        # 1.5R target = 10150 → SL should go to entry + 0.5R = 10050
        pos = _position(entry=10_000.0, sl=9_900.0)
        candle = _candle(10_160.0)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(), candle)
        be = [i for i in intents if i.reason == ExitReason.SL_GLOBAL]
        assert len(be) == 1
        assert be[0].new_stop_loss >= Decimal("10050")

    def test_no_breakeven_after_lot_a_filled(self) -> None:
        pos = _position(entry=10_000.0, sl=9_900.0, lot_a_filled=True)
        candle = _candle(10_250.0)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(), candle)
        assert not any(i.reason == ExitReason.SL_GLOBAL for i in intents)

    def test_no_breakeven_when_sl_already_higher(self) -> None:
        # SL already at 10050, would-be new SL is 10020 → no update
        pos = _position(entry=10_000.0, sl=10_050.0)
        candle = _candle(10_105.0)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(), candle)
        assert not any(i.reason == ExitReason.SL_GLOBAL for i in intents)


# ── Priority: forced exits block non-forced ───────────────────────────────────

class TestPriority:
    def test_forced_exit_returns_early(self) -> None:
        # Death cross should prevent trailing/breakeven from appearing
        pos = _position(entry=10_000.0, high=10_400.0, lot_a_filled=True)
        snap_1h = _snapshot_1h(ema20=90.0, ema50=100.0)  # death cross
        intents = compute_exit_intents(pos, snap_1h, _snapshot_5m(atr=50.0), _candle(10_250.0))
        assert len(intents) == 1
        assert intents[0].reason == ExitReason.FORCED_DEATH_CROSS

    def test_no_intents_when_healthy_position(self) -> None:
        pos = _position(entry=10_000.0, high=10_050.0)
        # Normal market, price barely moved, lot A not filled
        candle = _candle(10_030.0)
        intents = compute_exit_intents(pos, _snapshot_1h(), _snapshot_5m(atr=50.0), candle)
        # No breakeven (price < 1R target of 10100), no trailing (lot A not filled)
        assert intents == []
