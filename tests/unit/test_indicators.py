from __future__ import annotations

import pytest

from tradebot.services.indicators.atr import atr
from tradebot.services.indicators.ema import ema
from tradebot.services.indicators.factory import CandleSample, build_indicator_snapshot
from tradebot.services.indicators.macd import macd
from tradebot.services.indicators.rsi import rsi, rsi_series

DAY_MS = 86_400_000
MINUTE_MS = 60_000


def _candle(close_time_ms: int, close: float, volume: float = 10.0) -> CandleSample:
    return CandleSample(
        open_time_ms=close_time_ms - MINUTE_MS,
        close_time_ms=close_time_ms,
        open=close - 0.5,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=volume,
    )


def _single_session_candles(
    count: int, start_price: float = 100.0
) -> list[CandleSample]:
    candles: list[CandleSample] = []
    for index in range(count):
        close_time_ms = (index + 1) * MINUTE_MS
        candles.append(_candle(close_time_ms, start_price + index, volume=10.0 + index))
    return candles


def _two_session_candles(
    previous_count: int = 20, current_count: int = 20
) -> list[CandleSample]:
    candles: list[CandleSample] = []
    for index in range(previous_count):
        close_time_ms = (index + 1) * MINUTE_MS
        candles.append(_candle(close_time_ms, 100.0 + index, volume=20.0 + index))

    for index in range(current_count):
        close_time_ms = DAY_MS + ((index + 1) * MINUTE_MS)
        candles.append(_candle(close_time_ms, 200.0 + index, volume=40.0 + index))
    return candles


def test_ema_uses_sma_seed_and_standard_alpha() -> None:
    value = ema([1, 2, 3, 4, 5], period=3)
    assert value == pytest.approx(4.0)


def test_rsi_stays_in_expected_bounds() -> None:
    increasing = [float(value) for value in range(1, 16)]
    decreasing = list(reversed(increasing))
    flat = [10.0] * 15

    assert rsi(increasing, period=14) == pytest.approx(100.0)
    assert rsi(decreasing, period=14) == pytest.approx(0.0)
    assert rsi(flat, period=14) == pytest.approx(50.0)


def test_rsi_requires_period_plus_one_points_for_first_value() -> None:
    values = [float(value) for value in range(1, 15)]
    assert all(item is None for item in rsi_series(values, period=14))

    with_first_rsi = rsi_series(values + [15.0], period=14)
    assert with_first_rsi[13] is None
    assert with_first_rsi[14] is not None


def test_atr_wilder_smoothing() -> None:
    highs = [10.0, 12.0, 13.0, 15.0]
    lows = [8.0, 10.0, 11.0, 14.0]
    closes = [9.0, 11.0, 12.0, 14.0]

    value = atr(highs, lows, closes, period=3)
    assert value == pytest.approx(2.5555555556)


def test_macd_returns_consistent_components() -> None:
    closes = [float(100 + value) for value in range(60)]
    payload = macd(closes)

    assert payload["hist"] == pytest.approx(payload["macd"] - payload["signal"])
    assert payload["macd"] > 0.0


def test_snapshot_marks_warmup_and_missing_history() -> None:
    candles = _single_session_candles(10)
    snapshot = build_indicator_snapshot(
        symbol="BTCUSDC", timeframe="1m", candles=candles, computed_at=123
    )

    assert snapshot["schema_version"] == "1.0.0"
    assert snapshot["computed_at"] == 123
    assert snapshot["rsi"] == {"status": "unavailable", "reason": "warmup"}
    assert snapshot["macd"]["hist"]["status"] == "unavailable"
    assert snapshot["pivots"]["pp"] == {
        "status": "unavailable",
        "reason": "missing_history",
    }
    assert snapshot["vwap"]["status"] == "available"


def test_snapshot_keeps_rsi_in_warmup_at_14_candles() -> None:
    candles = _single_session_candles(14)
    snapshot = build_indicator_snapshot(
        symbol="BTCUSDC", timeframe="1m", candles=candles, computed_at=124
    )

    assert snapshot["rsi"] == {"status": "unavailable", "reason": "warmup"}
    assert snapshot["atr"]["status"] == "available"


def test_snapshot_exposes_available_values_and_pivots() -> None:
    candles = _two_session_candles(previous_count=20, current_count=20)
    snapshot = build_indicator_snapshot(
        symbol="BTCUSDC", timeframe="1m", candles=candles, computed_at=456
    )

    assert snapshot["rsi"]["status"] == "available"
    assert snapshot["ema20"]["status"] == "available"
    assert snapshot["macd"]["hist"]["status"] == "available"
    assert snapshot["atr"]["status"] == "available"
    assert snapshot["adx"]["status"] == "available"
    assert snapshot["stoch_rsi"]["k"]["status"] == "available"
    assert 0.0 <= snapshot["stoch_rsi"]["k"]["value"] <= 1.0
    assert 0.0 <= snapshot["stoch_rsi"]["d"]["value"] <= 1.0

    pivots = snapshot["pivots"]
    assert pivots["pp"]["status"] == "available"
    assert pivots["pp"]["value"] == pytest.approx((120.0 + 99.0 + 119.0) / 3.0)
