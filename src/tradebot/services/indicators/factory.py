from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from time import time
from typing import Any, Sequence

from tradebot.services.indicators.atr import atr
from tradebot.services.indicators.ema import ema
from tradebot.services.indicators.macd import macd
from tradebot.services.indicators.rsi import rsi, rsi_series

DAY_MS = 86_400_000


@dataclass(frozen=True)
class CandleSample:
    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def _available(value: float) -> dict[str, Any]:
    return {"status": "available", "value": float(value)}


def _unavailable(reason: str) -> dict[str, Any]:
    return {"status": "unavailable", "reason": reason}


def _sma(values: Sequence[float], period: int) -> float:
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(values) < period:
        raise ValueError(
            f"insufficient data for sma(period={period}): got {len(values)} values"
        )
    window = values[-period:]
    return sum(window) / period


def _bollinger(
    values: Sequence[float], period: int = 20, width: float = 2.0
) -> dict[str, float]:
    middle = _sma(values, period)
    window = values[-period:]
    variance = sum((value - middle) ** 2 for value in window) / period
    stddev = sqrt(variance)
    return {
        "upper": middle + (width * stddev),
        "middle": middle,
        "lower": middle - (width * stddev),
    }


def _adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float:
    if period <= 0:
        raise ValueError("period must be > 0")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows and closes must have the same length")
    if len(closes) < (period * 2):
        raise ValueError(
            f"insufficient data for adx(period={period}): got {len(closes)} values"
        )

    plus_dm: list[float] = []
    minus_dm: list[float] = []
    tr_values: list[float] = []

    for index in range(1, len(closes)):
        up_move = highs[index] - highs[index - 1]
        down_move = lows[index - 1] - lows[index]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        tr_values.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
        )

    smooth_tr = sum(tr_values[:period]) / period
    smooth_plus_dm = sum(plus_dm[:period]) / period
    smooth_minus_dm = sum(minus_dm[:period]) / period

    dx_values: list[float] = []
    for index in range(period - 1, len(tr_values)):
        if index > period - 1:
            smooth_tr = ((smooth_tr * (period - 1)) + tr_values[index]) / period
            smooth_plus_dm = ((smooth_plus_dm * (period - 1)) + plus_dm[index]) / period
            smooth_minus_dm = (
                (smooth_minus_dm * (period - 1)) + minus_dm[index]
            ) / period

        plus_di = (100.0 * smooth_plus_dm / smooth_tr) if smooth_tr else 0.0
        minus_di = (100.0 * smooth_minus_dm / smooth_tr) if smooth_tr else 0.0
        denominator = plus_di + minus_di
        if denominator == 0.0:
            dx_values.append(0.0)
        else:
            dx_values.append(100.0 * abs(plus_di - minus_di) / denominator)

    if len(dx_values) < period:
        raise ValueError(
            f"insufficient data for adx(period={period}): got {len(closes)} values"
        )

    adx_value = sum(dx_values[:period]) / period
    for dx in dx_values[period:]:
        adx_value = ((adx_value * (period - 1)) + dx) / period
    return adx_value


def _stoch_rsi(
    values: Sequence[float],
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3,
) -> dict[str, float]:
    rsi_values = [
        value for value in rsi_series(values, rsi_period) if value is not None
    ]
    if not rsi_values:
        raise ValueError("insufficient data for stoch_rsi")

    raw_values: list[float] = []
    for index in range(stoch_period - 1, len(rsi_values)):
        window = rsi_values[index - stoch_period + 1 : index + 1]
        window_min = min(window)
        window_max = max(window)
        denominator = window_max - window_min
        if denominator == 0.0:
            raw_values.append(0.0)
        else:
            raw_values.append((rsi_values[index] - window_min) / denominator)

    if len(raw_values) < k_period:
        raise ValueError("insufficient data for stoch_rsi")

    k_values: list[float] = []
    for index in range(k_period - 1, len(raw_values)):
        window = raw_values[index - k_period + 1 : index + 1]
        k_values.append(sum(window) / k_period)

    if len(k_values) < d_period:
        raise ValueError("insufficient data for stoch_rsi")

    d_values: list[float] = []
    for index in range(d_period - 1, len(k_values)):
        window = k_values[index - d_period + 1 : index + 1]
        d_values.append(sum(window) / d_period)

    return {"k": k_values[-1], "d": d_values[-1]}


def _vwap(candles: Sequence[CandleSample]) -> float:
    latest_session = candles[-1].close_time_ms // DAY_MS
    session_candles = [
        candle for candle in candles if candle.close_time_ms // DAY_MS == latest_session
    ]
    total_volume = sum(candle.volume for candle in session_candles)
    if total_volume <= 0:
        raise ValueError("cannot compute vwap with zero volume")

    weighted_price_sum = 0.0
    for candle in session_candles:
        typical_price = (candle.high + candle.low + candle.close) / 3.0
        weighted_price_sum += typical_price * candle.volume
    return weighted_price_sum / total_volume


def _pivots(candles: Sequence[CandleSample]) -> dict[str, float]:
    latest_session = candles[-1].close_time_ms // DAY_MS
    previous_session = latest_session - 1
    previous_candles = [
        candle
        for candle in candles
        if candle.close_time_ms // DAY_MS == previous_session
    ]
    if not previous_candles:
        raise ValueError("missing previous session for pivots")

    high = max(candle.high for candle in previous_candles)
    low = min(candle.low for candle in previous_candles)
    close = sorted(previous_candles, key=lambda candle: candle.close_time_ms)[-1].close

    pp = (high + low + close) / 3.0
    return {
        "pp": pp,
        "r1": (2.0 * pp) - low,
        "s1": (2.0 * pp) - high,
        "r2": pp + (high - low),
        "s2": pp - (high - low),
        "r3": high + (2.0 * (pp - low)),
        "s3": low - (2.0 * (high - pp)),
    }


def _namespace_available(values: dict[str, float]) -> dict[str, dict[str, Any]]:
    return {key: _available(value) for key, value in values.items()}


def _namespace_unavailable(
    keys: Sequence[str], reason: str
) -> dict[str, dict[str, Any]]:
    return {key: _unavailable(reason) for key in keys}


def build_indicator_snapshot(
    *,
    symbol: str,
    timeframe: str,
    candles: Sequence[CandleSample],
    schema_version: str = "1.0.0",
    computed_at: int | None = None,
) -> dict[str, Any]:
    if not candles:
        raise ValueError("candles is required")

    sorted_candles = sorted(candles, key=lambda candle: candle.close_time_ms)
    closes = [float(candle.close) for candle in sorted_candles]
    highs = [float(candle.high) for candle in sorted_candles]
    lows = [float(candle.low) for candle in sorted_candles]

    snapshot: dict[str, Any] = {
        "schema_version": schema_version,
        "symbol": symbol,
        "timeframe": timeframe,
        "close_time": sorted_candles[-1].close_time_ms,
        "computed_at": computed_at if computed_at is not None else int(time() * 1000),
    }

    if len(closes) >= 15:
        snapshot["rsi"] = _available(rsi(closes, period=14))
    else:
        snapshot["rsi"] = _unavailable("warmup")

    if len(closes) >= 14:
        snapshot["atr"] = _available(atr(highs, lows, closes, period=14))
    else:
        snapshot["atr"] = _unavailable("warmup")

    if len(closes) >= 20:
        snapshot["ema20"] = _available(ema(closes, period=20))
        snapshot["bollinger"] = _namespace_available(
            _bollinger(closes, period=20, width=2.0)
        )
    else:
        snapshot["ema20"] = _unavailable("warmup")
        snapshot["bollinger"] = _namespace_unavailable(
            ("upper", "middle", "lower"), "warmup"
        )

    if len(closes) >= 50:
        snapshot["ema50"] = _available(ema(closes, period=50))
    else:
        snapshot["ema50"] = _unavailable("warmup")

    if len(closes) >= 200:
        snapshot["ema200"] = _available(ema(closes, period=200))
    else:
        snapshot["ema200"] = _unavailable("warmup")

    if len(closes) >= 9:
        snapshot["sma9"] = _available(_sma(closes, period=9))
    else:
        snapshot["sma9"] = _unavailable("warmup")

    if len(closes) >= 21:
        snapshot["sma21"] = _available(_sma(closes, period=21))
    else:
        snapshot["sma21"] = _unavailable("warmup")

    if len(closes) >= 35:
        snapshot["macd"] = _namespace_available(
            macd(closes, fast_period=12, slow_period=26, signal=9)
        )
    else:
        snapshot["macd"] = _namespace_unavailable(("macd", "signal", "hist"), "warmup")

    try:
        snapshot["vwap"] = _available(_vwap(sorted_candles))
    except ValueError:
        snapshot["vwap"] = _unavailable("missing_history")

    if len(closes) >= 28:
        snapshot["adx"] = _available(_adx(highs, lows, closes, period=14))
    else:
        snapshot["adx"] = _unavailable("warmup")

    if len(closes) >= 31:
        snapshot["stoch_rsi"] = _namespace_available(
            _stoch_rsi(
                closes,
                rsi_period=14,
                stoch_period=14,
                k_period=3,
                d_period=3,
            )
        )
    else:
        snapshot["stoch_rsi"] = _namespace_unavailable(("k", "d"), "warmup")

    try:
        snapshot["pivots"] = _namespace_available(_pivots(sorted_candles))
    except ValueError:
        snapshot["pivots"] = _namespace_unavailable(
            ("pp", "r1", "r2", "r3", "s1", "s2", "s3"), "missing_history"
        )

    return snapshot
