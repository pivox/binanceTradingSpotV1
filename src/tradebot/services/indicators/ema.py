from __future__ import annotations

from typing import Sequence


def ema_series(values: Sequence[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be > 0")

    if len(values) < period:
        return [None] * len(values)

    values_as_float = [float(value) for value in values]
    alpha = 2.0 / (period + 1.0)
    seed = sum(values_as_float[:period]) / period

    result: list[float | None] = [None] * (period - 1)
    result.append(seed)

    ema_value = seed
    for value in values_as_float[period:]:
        ema_value = ((value - ema_value) * alpha) + ema_value
        result.append(ema_value)
    return result


def ema(values: Sequence[float], period: int) -> float:
    series = ema_series(values, period)
    last_value = series[-1] if series else None
    if last_value is None:
        raise ValueError(
            f"insufficient data for ema(period={period}): got {len(values)} values"
        )
    return last_value
