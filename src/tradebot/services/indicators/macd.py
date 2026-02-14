from __future__ import annotations

from typing import Sequence

from tradebot.services.indicators.ema import ema, ema_series


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
    fast_ema = ema_series(values_f, fast_period)
    slow_ema = ema_series(values_f, slow_period)
    macd_values = [
        fast - slow
        for fast, slow in zip(fast_ema, slow_ema)
        if fast is not None and slow is not None
    ]

    signal_line = ema(macd_values, signal)
    macd_line = macd_values[-1]
    hist = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "hist": hist}
