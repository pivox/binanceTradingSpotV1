from __future__ import annotations

from typing import Sequence

from tradebot.services.indicators.ema import ema


def macd(
    values: Sequence[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal: int = 9,
) -> dict[str, float]:
    if fast_period <= 0 or slow_period <= 0 or signal <= 0:
        raise ValueError("period values must be > 0")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be < slow_period")
    if len(values) < (slow_period + signal):
        raise ValueError(
            "insufficient data for macd "
            f"(slow={slow_period}, signal={signal}): got {len(values)} values"
        )

    values_f = [float(value) for value in values]
    macd_values: list[float] = []
    for index in range(slow_period, len(values_f) + 1):
        subset = values_f[:index]
        fast = ema(subset, fast_period)
        slow = ema(subset, slow_period)
        macd_values.append(fast - slow)

    signal_line = ema(macd_values, signal)
    macd_line = macd_values[-1]
    hist = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "hist": hist}
