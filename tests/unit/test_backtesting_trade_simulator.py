"""Unit tests — SL/TP computation and exit simulation (Phase 2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tradebot.domain.models.candle import Candle
from tradebot.services.backtesting.models import BacktestConfig
from tradebot.services.backtesting.trade_simulator import compute_sl_tp, simulate_exit


def _av(v: float) -> dict:
    return {"status": "available", "value": v}


def _unavail() -> dict:
    return {"status": "unavailable", "reason": "missing_history"}


def _snap(
    close: float = 50_000.0,
    s1: float | None = 48_000.0,
    s2: float | None = 47_000.0,
    atr: float | None = 500.0,
) -> dict:
    pivots: dict = {
        "pp": _av(50_000.0),
        "r1": _av(52_000.0),
        "r2": _av(53_000.0),
        "s1": _av(s1) if s1 is not None else _unavail(),
        "s2": _av(s2) if s2 is not None else _unavail(),
    }
    snap: dict = {"close_price": close, "pivots": pivots}
    snap["atr"] = _av(atr) if atr is not None else _unavail()
    return snap


def _candle(open_time_ms: int, high: float, low: float, close: float = 0.0) -> Candle:
    c = close or (high + low) / 2
    return Candle(
        symbol="BTCUSDC",
        timeframe="5m",
        open_time_ms=open_time_ms,
        close_time_ms=open_time_ms + 5 * 60 * 1_000 - 1,
        open=Decimal(str(c)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(c)),
        volume=Decimal("10.0"),
        is_partial=False,
    )


class TestComputeSlTp:
    def test_pivot_sl_closest_below_entry(self):
        # entry=50_000, s1=49_500 (1.0% below) → dist_raw < 2% max → PIVOT used
        # s2=48_000 is further but s1 is closest → s1 wins
        sl, tp, method = compute_sl_tp(
            50_000.0,
            _snap(close=50_000.0, s1=49_500.0, s2=48_000.0),
            BacktestConfig(),
        )
        assert method == "PIVOT"
        expected_sl = 49_500.0 * (1.0 - 0.003)
        assert sl == pytest.approx(expected_sl, rel=1e-6)
        assert tp == pytest.approx(50_000.0 + (50_000.0 - sl) * 1.5, rel=1e-6)

    def test_pivot_sl_distance_within_max(self):
        sl, tp, method = compute_sl_tp(49_500.0, _snap(), BacktestConfig())
        dist = (49_500.0 - sl) / 49_500.0
        assert dist <= 0.02

    def test_pivot_too_far_falls_back_to_atr(self):
        # s1 = 46_000, s2 = 45_000 → both > 2% below 49_500 → ATR fallback
        sl, tp, method = compute_sl_tp(
            49_500.0,
            _snap(s1=46_000.0, s2=45_000.0, atr=300.0),
            BacktestConfig(),
        )
        assert method == "ATR_FALLBACK"
        assert sl == pytest.approx(49_500.0 - 300.0 * 2.0, rel=1e-6)

    def test_atr_fallback_no_pivots(self):
        sl, tp, method = compute_sl_tp(
            50_000.0, _snap(s1=None, s2=None, atr=400.0), BacktestConfig()
        )
        assert method == "ATR_FALLBACK"
        assert sl == pytest.approx(50_000.0 - 400.0 * 2.0, rel=1e-6)

    def test_atr_clamped_to_max_sl(self):
        # ATR very large → SL would be > 2% → clamp
        sl, tp, method = compute_sl_tp(
            50_000.0, _snap(s1=None, s2=None, atr=2_000.0), BacktestConfig()
        )
        assert method == "ATR_FALLBACK"
        assert sl == pytest.approx(50_000.0 * 0.98, rel=1e-6)

    def test_no_pivot_no_atr_raises(self):
        snap = {"close_price": 50_000.0, "atr": _unavail()}
        with pytest.raises(ValueError, match="cannot compute SL"):
            compute_sl_tp(50_000.0, snap, BacktestConfig())

    def test_pivot_above_entry_ignored(self):
        # s1 above entry → must not be used
        sl, tp, method = compute_sl_tp(
            49_000.0,
            _snap(s1=50_000.0, s2=48_000.0, atr=200.0),
            BacktestConfig(),
        )
        # s1=50_000 > entry → skip; s2=48_000 < entry → use
        expected_sl = 48_000.0 * (1.0 - 0.003)
        dist = (49_000.0 - expected_sl) / 49_000.0
        if dist <= 0.02:
            assert method == "PIVOT"
        else:
            assert method == "ATR_FALLBACK"

    def test_tp_ratio(self):
        sl, tp, method = compute_sl_tp(
            50_000.0, _snap(), BacktestConfig(r_multiple=2.0)
        )
        dist = 50_000.0 - sl
        assert tp == pytest.approx(50_000.0 + dist * 2.0, rel=1e-6)


class TestSimulateExit:
    def test_tp_hit(self):
        candles = [
            _candle(1000, high=50_800.0, low=49_700.0),  # TP@51_500 not reached
            _candle(2000, high=51_600.0, low=50_000.0),  # TP hit
        ]
        _, exit_price, reason, _, _ = simulate_exit(
            50_000.0, 49_000.0, 51_500.0, candles
        )
        assert reason == "TP"
        assert exit_price == pytest.approx(51_500.0)

    def test_sl_hit(self):
        candles = [
            _candle(1000, high=50_200.0, low=49_100.0),  # SL@49_000 not reached
            _candle(2000, high=49_600.0, low=48_800.0),  # SL hit
        ]
        _, exit_price, reason, _, _ = simulate_exit(
            50_000.0, 49_000.0, 51_500.0, candles
        )
        assert reason == "SL"
        assert exit_price == pytest.approx(49_000.0)

    def test_sl_before_tp_same_candle(self):
        # Candle spans both SL and TP → pessimistic: SL wins
        candles = [_candle(1000, high=52_000.0, low=48_800.0)]
        _, _, reason, _, _ = simulate_exit(50_000.0, 49_000.0, 51_500.0, candles)
        assert reason == "SL"

    def test_open_trade(self):
        candles = [_candle(1000, high=50_500.0, low=49_600.0)]
        exit_ms, exit_price, reason, _, _ = simulate_exit(
            50_000.0, 49_000.0, 51_500.0, candles
        )
        assert reason == "OPEN"
        assert exit_ms is None
        assert exit_price is None

    def test_no_candles(self):
        exit_ms, exit_price, reason, mfe, mae = simulate_exit(
            50_000.0, 49_000.0, 51_500.0, []
        )
        assert reason == "OPEN"
        assert mfe == 0.0
        assert mae == 0.0

    def test_mfe_tracking(self):
        candles = [
            _candle(1000, high=50_800.0, low=49_700.0),  # mfe = 1.6%, mae = 0.6%
            _candle(2000, high=51_000.0, low=49_500.0),  # mfe = 2.0%, mae = 1.0%
        ]
        _, _, _, mfe, mae = simulate_exit(50_000.0, 49_000.0, 51_500.0, candles)
        assert mfe == pytest.approx(2.0, rel=1e-4)
        assert mae == pytest.approx(1.0, rel=1e-4)

    def test_exit_time_is_close_time_of_candle(self):
        candle = _candle(10_000, high=51_600.0, low=50_100.0)
        exit_ms, _, _, _, _ = simulate_exit(50_000.0, 49_000.0, 51_500.0, [candle])
        assert exit_ms == candle.close_time_ms

    def test_sl_gap_exit_at_open_price(self):
        # Candle opens below SL (gap down) → exit at open, not at stop_loss
        candle = _candle(1000, high=49_100.0, low=48_700.0, close=48_800.0)
        # Override open to gap below SL
        from decimal import Decimal

        gap_candle = Candle(
            symbol="BTCUSDC",
            timeframe="5m",
            open_time_ms=1000,
            close_time_ms=1000 + 5 * 60 * 1_000 - 1,
            open=Decimal("48_800.0"),
            high=Decimal("49_100.0"),
            low=Decimal("48_700.0"),
            close=Decimal("48_800.0"),
            volume=Decimal("10.0"),
            is_partial=False,
        )
        _, exit_price, reason, _, _ = simulate_exit(
            50_000.0, 49_000.0, 51_500.0, [gap_candle]
        )
        assert reason == "SL"
        assert exit_price == pytest.approx(48_800.0)  # at open, not 49_000

    def test_tp_gap_exit_at_open_price(self):
        # Candle opens above TP (gap up) → exit at open, not at take_profit
        from decimal import Decimal

        gap_candle = Candle(
            symbol="BTCUSDC",
            timeframe="5m",
            open_time_ms=1000,
            close_time_ms=1000 + 5 * 60 * 1_000 - 1,
            open=Decimal("52_000.0"),
            high=Decimal("52_500.0"),
            low=Decimal("51_800.0"),
            close=Decimal("52_000.0"),
            volume=Decimal("10.0"),
            is_partial=False,
        )
        _, exit_price, reason, _, _ = simulate_exit(
            50_000.0, 49_000.0, 51_500.0, [gap_candle]
        )
        assert reason == "TP"
        assert exit_price == pytest.approx(52_000.0)  # at open, not 51_500
