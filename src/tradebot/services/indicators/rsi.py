from __future__ import annotations

from typing import Sequence


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0 and avg_gain == 0.0:
        return 50.0
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def rsi_series(values: Sequence[float], period: int = 14) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be > 0")

    required_points = period + 1
    if len(values) < required_points:
        return [None] * len(values)

    closes = [float(value) for value in values]
    result: list[float | None] = [None] * len(closes)

    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, required_points):
        delta = closes[index] - closes[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    result[period] = _rsi_from_averages(avg_gain, avg_loss)

    for index in range(required_points, len(closes)):
        delta = closes[index] - closes[index - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        result[index] = _rsi_from_averages(avg_gain, avg_loss)

    return result


def rsi(values: Sequence[float], period: int = 14) -> float:
    series = rsi_series(values, period)
    last_value = series[-1] if series else None
    if last_value is None:
        raise ValueError(
            f"insufficient data for rsi(period={period}): got {len(values)} values"
        )
    return last_value
