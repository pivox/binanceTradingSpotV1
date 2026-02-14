from __future__ import annotations

from typing import Sequence


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float:
    if period <= 0:
        raise ValueError("period must be > 0")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows and closes must have the same length")
    if len(highs) < period:
        raise ValueError(
            f"insufficient data for atr(period={period}): got {len(highs)} values"
        )

    highs_f = [float(value) for value in highs]
    lows_f = [float(value) for value in lows]
    closes_f = [float(value) for value in closes]

    tr_values: list[float] = []
    for index in range(len(highs_f)):
        if index == 0:
            tr_values.append(highs_f[index] - lows_f[index])
            continue
        true_range = max(
            highs_f[index] - lows_f[index],
            abs(highs_f[index] - closes_f[index - 1]),
            abs(lows_f[index] - closes_f[index - 1]),
        )
        tr_values.append(true_range)

    atr_value = sum(tr_values[:period]) / period
    for true_range in tr_values[period:]:
        atr_value = ((atr_value * (period - 1)) + true_range) / period
    return atr_value
