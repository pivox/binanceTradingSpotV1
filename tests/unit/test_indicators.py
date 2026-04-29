from __future__ import annotations

import pytest

from tradebot.services.indicators.adx import adx
from tradebot.services.indicators.atr import atr
from tradebot.services.indicators.ema import ema
from tradebot.services.indicators.factory import CandleSample, build_indicator_snapshot
from tradebot.services.indicators.macd import macd
from tradebot.services.indicators.rsi import rsi, rsi_series
from tradebot.services.indicators.vwap import vwap

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


def test_adx_returns_value_in_valid_range() -> None:
    n = 40
    highs = [100.0 + i * 0.5 for i in range(n)]
    lows = [99.0 + i * 0.5 for i in range(n)]
    closes = [99.5 + i * 0.5 for i in range(n)]

    value = adx(highs, lows, closes, period=14)
    assert 0.0 <= value <= 100.0


def test_adx_raises_on_insufficient_data() -> None:
    with pytest.raises(ValueError, match="insufficient data"):
        adx([1.0] * 10, [0.9] * 10, [0.95] * 10, period=14)


def test_adx_raises_on_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        adx([1.0, 2.0], [1.0], [1.0, 2.0], period=14)


def test_vwap_uses_only_current_session() -> None:
    # previous session (day 0)
    prev_highs = [101.0, 102.0]
    prev_lows = [99.0, 100.0]
    prev_closes = [100.0, 101.0]
    prev_volumes = [1000.0, 1000.0]
    prev_times = [int(DAY_MS * 0.4), int(DAY_MS * 0.8)]

    # current session (day 1) — typical price 200, volume 500
    cur_highs = [201.0, 202.0]
    cur_lows = [199.0, 200.0]
    cur_closes = [200.0, 201.0]
    cur_volumes = [500.0, 500.0]
    cur_times = [DAY_MS + int(DAY_MS * 0.2), DAY_MS + int(DAY_MS * 0.4)]

    all_highs = prev_highs + cur_highs
    all_lows = prev_lows + cur_lows
    all_closes = prev_closes + cur_closes
    all_volumes = prev_volumes + cur_volumes
    all_times = prev_times + cur_times

    result = vwap(all_highs, all_lows, all_closes, all_volumes, all_times)

    # VWAP must reflect only current session candles, not previous session
    expected_tp1 = (201.0 + 199.0 + 200.0) / 3.0
    expected_tp2 = (202.0 + 200.0 + 201.0) / 3.0
    expected = (expected_tp1 * 500.0 + expected_tp2 * 500.0) / 1000.0
    assert result == pytest.approx(expected)


def test_vwap_raises_on_zero_volume() -> None:
    times = [int(DAY_MS * 0.5), int(DAY_MS * 0.6)]
    with pytest.raises(ValueError, match="zero volume"):
        vwap([100.0, 101.0], [99.0, 100.0], [100.0, 101.0], [0.0, 0.0], times)


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
