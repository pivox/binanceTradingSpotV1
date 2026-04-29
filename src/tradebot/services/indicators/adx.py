from __future__ import annotations

from typing import Sequence


def adx(
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
